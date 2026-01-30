"""Submodule transformer for GitLab to GitHub migration"""

import re
from typing import Any, Dict, List, Optional
from .base_transformer import BaseTransformer, TransformationResult


class SubmoduleTransformer(BaseTransformer):
    """
    Transform GitLab submodule URLs to GitHub equivalents.
    
    Handles:
    - Parsing .gitmodules file content
    - Rewriting URLs for migrated repositories
    - Identifying external submodules (not being migrated)
    - Supporting SSH, HTTPS, and relative URL formats
    """
    
    def __init__(self):
        super().__init__("SubmoduleTransformer")
    
    def transform(self, input_data: Dict[str, Any]) -> TransformationResult:
        """
        Transform submodule URLs based on migration mappings.
        
        Args:
            input_data: Dict with:
                - gitmodules_content: Content of .gitmodules file (str)
                - url_mappings: Dict mapping GitLab URLs to GitHub URLs
                  Format: {"gitlab.com/org/repo": "github.com/org/repo"}
        
        Returns:
            TransformationResult with:
                - submodules: List of parsed and transformed submodules
                - gitmodules_content: Updated .gitmodules file content
                - warnings: List of submodules not being migrated
        """
        self.log_transform_start("submodules")
        
        # Validate input
        validation = self.validate_input(input_data, ["gitmodules_content"])
        if not validation.success:
            return validation
        
        gitmodules_content = input_data["gitmodules_content"]
        url_mappings = input_data.get("url_mappings", {})
        
        result = TransformationResult(success=True, data={})
        
        # Parse .gitmodules
        submodules = self._parse_gitmodules(gitmodules_content)
        
        if not submodules:
            result.add_warning("No submodules found in .gitmodules")
            result.data = {
                "submodules": [],
                "gitmodules_content": gitmodules_content,
                "rewrite_count": 0
            }
            self.log_transform_complete(True, "No submodules to transform")
            return result
        
        # Rewrite URLs
        rewritten_submodules = self._rewrite_submodule_urls(submodules, url_mappings)
        
        # Generate updated .gitmodules content
        updated_content = self._generate_gitmodules(rewritten_submodules)
        
        # Collect statistics
        rewrite_count = sum(1 for sub in rewritten_submodules if sub.get("rewritten", False))
        external_count = len(rewritten_submodules) - rewrite_count
        
        # Add warnings for external submodules
        for sub in rewritten_submodules:
            if not sub.get("rewritten", False):
                result.add_warning(
                    f"Submodule '{sub['name']}' URL not rewritten - repository not being migrated",
                    {"url": sub.get("url", ""), "path": sub.get("path", "")}
                )
        
        result.data = {
            "submodules": rewritten_submodules,
            "gitmodules_content": updated_content,
            "rewrite_count": rewrite_count,
            "external_count": external_count,
            "total_count": len(rewritten_submodules)
        }
        
        self.log_transform_complete(
            True, 
            f"Transformed {len(rewritten_submodules)} submodules ({rewrite_count} rewritten, {external_count} external)"
        )
        
        return result
    
    def _parse_gitmodules(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse .gitmodules file content.
        
        Args:
            content: Raw .gitmodules file content
            
        Returns:
            List of submodule dicts with name, path, url, etc.
        """
        submodules = []
        current = {}
        
        for line in content.splitlines():
            line = line.strip()
            
            # New submodule section
            if line.startswith('[submodule'):
                if current:
                    submodules.append(current)
                # Extract name from [submodule "name"]
                match = re.search(r'\[submodule\s+"([^"]+)"\]', line)
                if match:
                    current = {"name": match.group(1)}
                else:
                    current = {"name": "unnamed"}
            # Key-value pair
            elif '=' in line and current:
                key, value = line.split('=', 1)
                current[key.strip()] = value.strip()
        
        # Don't forget the last submodule
        if current:
            submodules.append(current)
        
        return submodules
    
    def _rewrite_submodule_urls(
        self, 
        submodules: List[Dict[str, Any]], 
        url_mappings: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        Rewrite submodule URLs based on migration mappings.
        
        Args:
            submodules: List of parsed submodules
            url_mappings: Dict mapping GitLab patterns to GitHub patterns
            
        Returns:
            List of submodules with rewritten URLs where applicable
        """
        rewritten_submodules = []
        
        for sub in submodules:
            sub_copy = sub.copy()
            old_url = sub.get("url", "")
            
            if not old_url:
                sub_copy["rewritten"] = False
                sub_copy["warning"] = "No URL specified"
                rewritten_submodules.append(sub_copy)
                continue
            
            # Normalize the URL for comparison (remove protocol, trailing .git, etc.)
            normalized_old_url = self._normalize_url(old_url)
            
            # Check if this repo is being migrated
            rewritten = False
            for gitlab_pattern, github_pattern in url_mappings.items():
                normalized_gitlab = self._normalize_url(gitlab_pattern)
                
                if normalized_gitlab in normalized_old_url:
                    # Rewrite the URL
                    new_url = self._rewrite_url(old_url, gitlab_pattern, github_pattern)
                    sub_copy["url"] = new_url
                    sub_copy["rewritten"] = True
                    sub_copy["original_url"] = old_url
                    rewritten = True
                    break
            
            if not rewritten:
                # Not being migrated - flag for user attention
                sub_copy["rewritten"] = False
                sub_copy["warning"] = "Submodule repository not being migrated"
            
            rewritten_submodules.append(sub_copy)
        
        return rewritten_submodules
    
    def _normalize_url(self, url: str) -> str:
        """
        Normalize a Git URL for comparison.
        
        Handles:
        - Removing protocol (https://, git@, ssh://)
        - Removing trailing .git
        - Converting SSH format to standard path
        
        Args:
            url: Git URL to normalize
            
        Returns:
            Normalized URL string
        """
        normalized = url.lower()
        
        # Remove common protocols
        normalized = re.sub(r'^https?://', '', normalized)
        normalized = re.sub(r'^ssh://', '', normalized)
        normalized = re.sub(r'^git@', '', normalized)
        
        # Convert SSH format (git@host:path) to slash format (host/path)
        normalized = re.sub(r':(?=[^/])', '/', normalized)
        
        # Remove trailing .git
        normalized = re.sub(r'\.git$', '', normalized)
        
        # Remove trailing slash
        normalized = normalized.rstrip('/')
        
        return normalized
    
    def _rewrite_url(self, original_url: str, gitlab_pattern: str, github_pattern: str) -> str:
        """
        Rewrite a URL from GitLab to GitHub format, preserving the original format.
        
        Args:
            original_url: Original URL (SSH, HTTPS, or relative)
            gitlab_pattern: GitLab URL pattern to match
            github_pattern: GitHub URL pattern to replace with
            
        Returns:
            Rewritten URL in the same format as original
        """
        # Detect URL format
        is_ssh = original_url.startswith('git@') or ':' in original_url and '://' not in original_url
        is_https = original_url.startswith('http://') or original_url.startswith('https://')
        has_git_extension = original_url.endswith('.git')
        
        # Normalize patterns for replacement
        gitlab_norm = self._normalize_url(gitlab_pattern)
        github_norm = self._normalize_url(github_pattern)
        original_norm = self._normalize_url(original_url)
        
        # Replace the pattern
        new_url_norm = original_norm.replace(gitlab_norm, github_norm)
        
        # Reconstruct URL in original format
        if is_ssh:
            # SSH format: git@github.com:owner/repo.git
            parts = new_url_norm.split('/', 1)
            if len(parts) == 2:
                host, path = parts
                new_url = f"git@{host}:{path}"
            else:
                new_url = f"git@{new_url_norm}"
        elif is_https:
            # HTTPS format: https://github.com/owner/repo.git
            new_url = f"https://{new_url_norm}"
        else:
            # Relative or other format - keep as is
            new_url = new_url_norm
        
        # Add .git extension if original had it
        if has_git_extension and not new_url.endswith('.git'):
            new_url += '.git'
        
        return new_url
    
    def _generate_gitmodules(self, submodules: List[Dict[str, Any]]) -> str:
        """
        Generate .gitmodules file content from submodule list.
        
        Args:
            submodules: List of submodule dicts
            
        Returns:
            Formatted .gitmodules file content
        """
        lines = []
        
        for sub in submodules:
            name = sub.get("name", "")
            lines.append(f'[submodule "{name}"]')
            
            # Add other properties in order (path, url, then others)
            if "path" in sub:
                lines.append(f'\tpath = {sub["path"]}')
            if "url" in sub:
                lines.append(f'\turl = {sub["url"]}')
            
            # Add any other properties (except metadata we added)
            for key, value in sub.items():
                if key not in ["name", "path", "url", "rewritten", "warning", "original_url"]:
                    lines.append(f'\t{key} = {value}')
            
            lines.append('')  # Empty line between submodules
        
        return '\n'.join(lines)
