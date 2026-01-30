"""User mapping transformer for GitLab to GitHub user identity resolution"""

from typing import Any, Dict, List, Optional, Tuple
from difflib import SequenceMatcher
from .base_transformer import BaseTransformer, TransformationResult


class UserMapper(BaseTransformer):
    """
    Map GitLab users to GitHub users with confidence scoring.
    
    Handles:
    - Email-based matching
    - Username matching (case-insensitive)
    - Organization membership cross-reference
    - Confidence level calculation
    - Unmapped user identification
    """
    
    def __init__(self):
        super().__init__("UserMapper")
        self.unmapped_users: List[Dict[str, Any]] = []
    
    def transform(self, input_data: Dict[str, Any]) -> TransformationResult:
        """
        Map GitLab users to GitHub users.
        
        Args:
            input_data: Dict with:
                - 'gitlab_users': List of GitLab user dicts
                - 'github_users': List of GitHub user dicts (optional)
                - 'github_org_members': List of GitHub org members (optional)
            
        Returns:
            TransformationResult with user mappings
        """
        self.log_transform_start("User Mapping")
        result = TransformationResult(success=True)
        
        # Validate input
        validation = self.validate_input(input_data, ["gitlab_users"])
        if not validation.success:
            return validation
        
        try:
            gitlab_users = input_data["gitlab_users"]
            github_users = input_data.get("github_users", [])
            github_org_members = input_data.get("github_org_members", [])
            
            # Combine GitHub users and org members
            all_github_users = self._combine_github_users(github_users, github_org_members)
            
            # Create mappings
            mappings = []
            stats = {
                "total": len(gitlab_users),
                "high_confidence": 0,
                "medium_confidence": 0,
                "low_confidence": 0,
                "unmapped": 0
            }
            
            for gitlab_user in gitlab_users:
                mapping = self._map_user(gitlab_user, all_github_users)
                mappings.append(mapping)
                
                # Update stats
                confidence = mapping.get("confidence", "unmapped")
                if confidence == "high":
                    stats["high_confidence"] += 1
                elif confidence == "medium":
                    stats["medium_confidence"] += 1
                elif confidence == "low":
                    stats["low_confidence"] += 1
                else:
                    stats["unmapped"] += 1
            
            result.data = {
                "mappings": mappings,
                "stats": stats,
                "unmapped_users": self.unmapped_users
            }
            
            result.metadata.update(stats)
            
            # Add warnings for unmapped users
            if self.unmapped_users:
                result.add_warning(
                    f"{len(self.unmapped_users)} users could not be mapped",
                    {"unmapped_users": [u["gitlab"]["username"] for u in self.unmapped_users]}
                )
            
            self.log_transform_complete(
                True,
                f"Mapped {stats['high_confidence'] + stats['medium_confidence']}/{stats['total']} users"
            )
            
        except Exception as e:
            result.add_error(f"User mapping error: {str(e)}")
            self.log_transform_complete(False, str(e))
        
        return result
    
    def _combine_github_users(
        self,
        github_users: List[Dict[str, Any]],
        org_members: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Combine and deduplicate GitHub users"""
        seen_logins = set()
        combined = []
        
        for user in github_users + org_members:
            login = user.get("login")
            if login and login not in seen_logins:
                seen_logins.add(login)
                combined.append(user)
        
        return combined
    
    def _map_user(
        self,
        gitlab_user: Dict[str, Any],
        github_users: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Map a single GitLab user to GitHub user.
        
        Returns mapping dict with confidence level.
        """
        mapping = {
            "gitlab": {
                "id": gitlab_user.get("id"),
                "username": gitlab_user.get("username"),
                "email": gitlab_user.get("email"),
                "name": gitlab_user.get("name")
            },
            "github": None,
            "confidence": "unmapped",
            "method": "none",
            "confirmed_by_user": False
        }
        
        # Try email match first (highest confidence)
        github_match = self._match_by_email(gitlab_user, github_users)
        if github_match:
            mapping["github"] = {
                "login": github_match.get("login"),
                "id": github_match.get("id"),
                "email": github_match.get("email"),
                "name": github_match.get("name")
            }
            mapping["confidence"] = "high"
            mapping["method"] = "email"
            return mapping
        
        # Try username match (medium confidence)
        github_match = self._match_by_username(gitlab_user, github_users)
        if github_match:
            mapping["github"] = {
                "login": github_match.get("login"),
                "id": github_match.get("id"),
                "email": github_match.get("email"),
                "name": github_match.get("name")
            }
            mapping["confidence"] = "medium"
            mapping["method"] = "username"
            return mapping
        
        # Try name match (low confidence)
        github_match = self._match_by_name(gitlab_user, github_users)
        if github_match:
            mapping["github"] = {
                "login": github_match.get("login"),
                "id": github_match.get("id"),
                "email": github_match.get("email"),
                "name": github_match.get("name")
            }
            mapping["confidence"] = "low"
            mapping["method"] = "name"
            return mapping
        
        # No match found
        mapping["confidence"] = "unmapped"
        mapping["method"] = "none"
        self.unmapped_users.append(mapping)
        
        return mapping
    
    def _match_by_email(
        self,
        gitlab_user: Dict[str, Any],
        github_users: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Match GitLab user by email"""
        gitlab_email = gitlab_user.get("email")
        if not gitlab_email:
            return None
        
        gitlab_email = gitlab_email.lower().strip()
        
        for gh_user in github_users:
            gh_email = gh_user.get("email")
            if gh_email and gh_email.lower().strip() == gitlab_email:
                return gh_user
        
        return None
    
    def _match_by_username(
        self,
        gitlab_user: Dict[str, Any],
        github_users: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Match GitLab user by username - exact match first, then fuzzy"""
        gitlab_username = gitlab_user.get("username")
        if not gitlab_username:
            return None
        
        gitlab_username_lower = gitlab_username.lower().strip()
        
        # Try exact match first
        for gh_user in github_users:
            gh_login = gh_user.get("login")
            if gh_login and gh_login.lower().strip() == gitlab_username_lower:
                return gh_user
        
        # Try fuzzy match with high threshold
        best_match, best_score = self._fuzzy_match_username(gitlab_username, github_users)
        if best_match and best_score >= 0.75:  # Slightly lower threshold for usernames
            return best_match
        
        return None
    
    def _match_by_name(
        self,
        gitlab_user: Dict[str, Any],
        github_users: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Match GitLab user by name (low confidence) - exact match first, then fuzzy"""
        gitlab_name = gitlab_user.get("name")
        if not gitlab_name:
            return None
        
        gitlab_name_lower = gitlab_name.lower().strip()
        
        # Try exact match first
        for gh_user in github_users:
            gh_name = gh_user.get("name")
            if gh_name and gh_name.lower().strip() == gitlab_name_lower:
                return gh_user
        
        # Try fuzzy match with high threshold
        best_match, best_score = self._fuzzy_match_name(gitlab_name, github_users)
        if best_match and best_score >= 0.85:  # High threshold for name matching
            return best_match
        
        return None
    
    def get_mapping_summary(self, mappings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate summary of user mappings.
        
        Args:
            mappings: List of user mapping dicts
            
        Returns:
            Summary dict with statistics
        """
        summary = {
            "total_users": len(mappings),
            "mapped": 0,
            "unmapped": 0,
            "high_confidence": 0,
            "medium_confidence": 0,
            "low_confidence": 0,
            "by_method": {
                "email": 0,
                "username": 0,
                "name": 0,
                "none": 0
            }
        }
        
        for mapping in mappings:
            confidence = mapping.get("confidence", "unmapped")
            method = mapping.get("method", "none")
            
            if mapping.get("github"):
                summary["mapped"] += 1
            else:
                summary["unmapped"] += 1
            
            if confidence == "high":
                summary["high_confidence"] += 1
            elif confidence == "medium":
                summary["medium_confidence"] += 1
            elif confidence == "low":
                summary["low_confidence"] += 1
            
            summary["by_method"][method] = summary["by_method"].get(method, 0) + 1
        
        return summary
    
    def _fuzzy_match_name(
        self,
        gitlab_name: str,
        github_users: List[Dict[str, Any]]
    ) -> Tuple[Optional[Dict[str, Any]], float]:
        """
        Fuzzy match GitLab user name against GitHub users.
        
        Args:
            gitlab_name: GitLab user's full name
            github_users: List of GitHub users
            
        Returns:
            Tuple of (best_match_user, confidence_score)
        """
        if not gitlab_name:
            return None, 0.0
        
        gitlab_name_normalized = self._normalize_name(gitlab_name)
        best_match = None
        best_score = 0.0
        
        for gh_user in github_users:
            gh_name = gh_user.get("name")
            if not gh_name:
                continue
            
            gh_name_normalized = self._normalize_name(gh_name)
            score = self._calculate_similarity(gitlab_name_normalized, gh_name_normalized)
            
            if score > best_score:
                best_score = score
                best_match = gh_user
        
        return best_match, best_score
    
    def _fuzzy_match_username(
        self,
        gitlab_username: str,
        github_users: List[Dict[str, Any]]
    ) -> Tuple[Optional[Dict[str, Any]], float]:
        """
        Fuzzy match GitLab username against GitHub logins.
        
        Args:
            gitlab_username: GitLab username
            github_users: List of GitHub users
            
        Returns:
            Tuple of (best_match_user, confidence_score)
        """
        if not gitlab_username:
            return None, 0.0
        
        gitlab_username_normalized = self._normalize_username(gitlab_username)
        best_match = None
        best_score = 0.0
        
        for gh_user in github_users:
            gh_login = gh_user.get("login")
            if not gh_login:
                continue
            
            gh_login_normalized = self._normalize_username(gh_login)
            score = self._calculate_similarity(gitlab_username_normalized, gh_login_normalized)
            
            if score > best_score:
                best_score = score
                best_match = gh_user
        
        return best_match, best_score
    
    def _normalize_name(self, name: str) -> str:
        """
        Normalize a name for comparison.
        
        - Lowercase
        - Strip whitespace
        - Remove common punctuation
        """
        if not name:
            return ""
        
        normalized = name.lower().strip()
        # Remove common punctuation
        for char in ['.', '-', '_', ',']:
            normalized = normalized.replace(char, ' ')
        # Collapse multiple spaces
        normalized = ' '.join(normalized.split())
        return normalized
    
    def _normalize_username(self, username: str) -> str:
        """
        Normalize a username for comparison.
        
        - Lowercase
        - Strip whitespace
        - Remove dots, dashes, underscores
        """
        if not username:
            return ""
        
        normalized = username.lower().strip()
        # Remove separators commonly used in usernames
        for char in ['.', '-', '_']:
            normalized = normalized.replace(char, '')
        return normalized
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate similarity ratio between two strings.
        
        Uses SequenceMatcher for similarity scoring.
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            Similarity score from 0.0 to 1.0
        """
        if not str1 or not str2:
            return 0.0
        
        return SequenceMatcher(None, str1, str2).ratio()
