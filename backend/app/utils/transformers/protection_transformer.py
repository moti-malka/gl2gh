"""GitLab Branch Protection Rules to GitHub transformer"""

from typing import Any, Dict, List, Optional, Set
from .base_transformer import BaseTransformer, TransformationResult


class ProtectionRulesTransformer(BaseTransformer):
    """
    Transform GitLab branch protection rules to GitHub branch protection settings.
    
    GitLab Protection Levels:
    - 0: No access
    - 30: Developer + Maintainer
    - 40: Maintainer
    - 60: Admin
    
    GitHub Mappings:
    - push_access_levels -> restrictions (users/teams who can push)
    - merge_access_levels -> required_pull_request_reviews
    - approvals_required -> required_approving_review_count
    - code_owner_approval_required -> require_code_owner_reviews
    - allow_force_push -> allow_force_pushes
    - unprotect_access_level -> restrictions for protection changes
    """
    
    def __init__(self):
        super().__init__("ProtectionRulesTransformer")
        self.gaps: List[Dict[str, Any]] = []
    
    def transform(self, input_data: Dict[str, Any]) -> TransformationResult:
        """
        Transform GitLab protected branch data to GitHub protection settings.
        
        Args:
            input_data: Dict with:
                - 'protected_branches': List of GitLab protected branch objects
                - 'protected_tags': List of GitLab protected tag objects (optional)
                - 'project_members': List of project members for user mapping (optional)
                - 'ci_jobs': List of CI job names for status checks (optional)
                - 'approval_rules': List of approval rules for CODEOWNERS (optional)
                
        Returns:
            TransformationResult with GitHub protection settings
        """
        self.log_transform_start("Branch Protection Rules")
        result = TransformationResult(success=True)
        self.gaps = []
        
        # Validate input
        validation = self.validate_input(input_data, ["protected_branches"])
        if not validation.success:
            return validation
        
        try:
            protected_branches = input_data["protected_branches"]
            protected_tags = input_data.get("protected_tags", [])
            project_members = input_data.get("project_members", [])
            ci_jobs = input_data.get("ci_jobs", [])
            approval_rules = input_data.get("approval_rules", [])
            
            # Transform each protected branch
            github_protections = []
            for branch in protected_branches:
                protection = self._transform_branch_protection(
                    branch, 
                    project_members,
                    ci_jobs
                )
                github_protections.append(protection)
            
            # Generate CODEOWNERS content if approval rules key is present
            codeowners_content = None
            if "approval_rules" in input_data:
                codeowners_content = self._generate_codeowners(approval_rules, project_members)
            
            result.data = {
                "branch_protections": github_protections,
                "codeowners_content": codeowners_content,
                "protected_tags": self._transform_protected_tags(protected_tags),
                "gaps": self.gaps
            }
            
            result.metadata["branches_protected"] = len(github_protections)
            result.metadata["tags_protected"] = len(protected_tags)
            result.metadata["conversion_gaps"] = len(self.gaps)
            result.metadata["has_codeowners"] = codeowners_content is not None
            
            # Add warnings for gaps
            for gap in self.gaps:
                result.add_warning(gap["message"], gap.get("context"))
            
            self.log_transform_complete(
                True, 
                f"Transformed {len(github_protections)} branch protections"
            )
            
        except Exception as e:
            result.add_error(f"Transformation error: {str(e)}")
            self.log_transform_complete(False, str(e))
        
        return result
    
    def _transform_branch_protection(
        self, 
        gitlab_branch: Dict[str, Any],
        project_members: List[Dict[str, Any]],
        ci_jobs: List[str]
    ) -> Dict[str, Any]:
        """
        Transform a single GitLab protected branch to GitHub protection settings.
        
        Args:
            gitlab_branch: GitLab protected branch object
            project_members: List of project members
            ci_jobs: List of CI job names for required status checks
            
        Returns:
            Dict with GitHub branch protection parameters
        """
        branch_name = gitlab_branch.get("name", "")
        
        # Initialize GitHub protection settings
        protection = {
            "branch": branch_name,
            "required_status_checks": None,
            "enforce_admins": False,
            "required_pull_request_reviews": None,
            "restrictions": None,
            "allow_force_pushes": False,
            "allow_deletions": False,
            "required_linear_history": False,
            "required_conversation_resolution": False,
        }
        
        # Map push access levels
        push_access_levels = gitlab_branch.get("push_access_levels", [])
        merge_access_levels = gitlab_branch.get("merge_access_levels", [])
        
        # Determine if force push is allowed
        allow_force_push = gitlab_branch.get("allow_force_push", False)
        protection["allow_force_pushes"] = allow_force_push
        
        # Map merge access levels to required reviews
        if merge_access_levels:
            protection["required_pull_request_reviews"] = self._map_merge_access_to_reviews(
                gitlab_branch,
                merge_access_levels
            )
        
        # Map code owner approval requirement
        code_owner_approval_required = gitlab_branch.get("code_owner_approval_required", False)
        if code_owner_approval_required and protection["required_pull_request_reviews"]:
            protection["required_pull_request_reviews"]["require_code_owner_reviews"] = True
        
        # Map CI jobs to required status checks
        if ci_jobs:
            protection["required_status_checks"] = {
                "strict": True,  # Require branches to be up to date before merging
                "contexts": ci_jobs  # List of CI job names that must pass
            }
        
        # Map unprotect access level (GitHub doesn't have direct equivalent)
        if "unprotect_access_level" in gitlab_branch and gitlab_branch["unprotect_access_level"] is not None:
            unprotect_access_level = gitlab_branch["unprotect_access_level"]
            self._add_gap(
                "unprotect_access_level",
                f"GitLab unprotect_access_level ({unprotect_access_level}) not directly mappable to GitHub",
                "medium",
                {"branch": branch_name, "access_level": unprotect_access_level}
            )
        
        # Check for restricted push access
        if push_access_levels:
            restricted_push = self._check_restricted_push(push_access_levels)
            if restricted_push:
                self._add_gap(
                    "push_restrictions",
                    f"GitLab push restrictions for '{branch_name}' require manual user/team mapping in GitHub",
                    "high",
                    {
                        "branch": branch_name,
                        "push_access_levels": push_access_levels,
                        "action": "Configure push restrictions in GitHub repository settings"
                    }
                )
        
        return protection
    
    def _map_merge_access_to_reviews(
        self,
        gitlab_branch: Dict[str, Any],
        merge_access_levels: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Map GitLab merge access levels to GitHub required reviews.
        
        Args:
            gitlab_branch: GitLab protected branch object
            merge_access_levels: List of merge access level objects
            
        Returns:
            Dict with required_pull_request_reviews settings
        """
        reviews = {
            "dismiss_stale_reviews": False,
            "require_code_owner_reviews": False,
            "required_approving_review_count": 1,
            "dismissal_restrictions": {}
        }
        
        # Check for approval requirements (GitLab Premium feature)
        # This data might come from approval_rules in the project
        approvals_before_merge = gitlab_branch.get("approvals_before_merge", 0)
        if approvals_before_merge > 0:
            reviews["required_approving_review_count"] = approvals_before_merge
        
        # Map merge access level restrictions
        # If access level is 40 (Maintainer), require at least 1 approval
        has_maintainer_only = any(
            level.get("access_level") == 40 
            for level in merge_access_levels
        )
        
        if has_maintainer_only and approvals_before_merge == 0:
            # Default to 1 approval if maintainer-only merge
            reviews["required_approving_review_count"] = 1
        
        return reviews
    
    def _check_restricted_push(self, push_access_levels: List[Dict[str, Any]]) -> bool:
        """
        Check if push access is restricted to specific users/groups.
        
        Args:
            push_access_levels: List of push access level objects
            
        Returns:
            True if push is restricted, False if open to all developers
        """
        # If there are specific user_id or group_id entries, it's restricted
        for level in push_access_levels:
            if level.get("user_id") or level.get("group_id"):
                return True
            # Access level 0 means no access (restricted)
            if level.get("access_level") == 0:
                return True
        
        return False
    
    def _transform_protected_tags(
        self, 
        protected_tags: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Transform GitLab protected tags to GitHub tag protection rules.
        
        Args:
            protected_tags: List of GitLab protected tag objects
            
        Returns:
            List of GitHub tag protection settings
        """
        github_tag_protections = []
        
        for tag in protected_tags:
            tag_name = tag.get("name", "")
            
            # GitHub has tag protection rules (requires GitHub Pro or Enterprise)
            protection = {
                "pattern": tag_name,
                "note": f"Migrated from GitLab protected tag: {tag_name}"
            }
            
            github_tag_protections.append(protection)
            
            # Add gap for tag protection limitations
            self._add_gap(
                "tag_protection",
                f"GitLab protected tag '{tag_name}' requires GitHub Pro/Enterprise for tag protection rules",
                "medium",
                {
                    "tag": tag_name,
                    "action": "Upgrade to GitHub Pro/Enterprise or manually protect tags"
                }
            )
        
        return github_tag_protections
    
    def _generate_codeowners(
        self,
        approval_rules: List[Dict[str, Any]],
        project_members: List[Dict[str, Any]]
    ) -> str:
        """
        Generate CODEOWNERS file from GitLab approval rules.
        
        Args:
            approval_rules: List of GitLab approval rule objects
            project_members: List of project members for username mapping
            
        Returns:
            CODEOWNERS file content
        """
        lines = [
            "# CODEOWNERS",
            "# Generated from GitLab approval rules",
            "# https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners",
            ""
        ]
        
        # Create member lookup
        member_lookup = {
            member.get("id"): member.get("username")
            for member in project_members
        }
        
        for rule in approval_rules:
            rule_name = rule.get("name", "")
            approvers = rule.get("eligible_approvers", [])
            groups = rule.get("groups", [])
            protected_branches = rule.get("protected_branches", [])
            
            # Build approvers list
            approver_list = []
            
            # Add individual approvers
            for approver in approvers:
                user_id = approver.get("id")
                username = member_lookup.get(user_id, approver.get("username"))
                if username:
                    approver_list.append(f"@{username}")
            
            # Add groups (teams in GitHub)
            for group in groups:
                group_path = group.get("path") or group.get("name")
                if group_path:
                    # GitHub teams format: @org/team-name
                    approver_list.append(f"@org/{group_path}")
            
            if not approver_list:
                continue
            
            # Determine file patterns
            file_pattern = rule.get("file_pattern", "*")
            if not file_pattern:
                file_pattern = "*"
            
            # Add comment for rule
            lines.append(f"# Rule: {rule_name}")
            lines.append(f"{file_pattern} {' '.join(approver_list)}")
            lines.append("")
        
        # Add default rule if no specific rules
        if len(lines) == 4:  # Only header comments
            lines.append("# Default: All files require review")
            lines.append("* @org/maintainers")
            lines.append("")
            
            self._add_gap(
                "codeowners_default",
                "No specific approval rules found, using default CODEOWNERS",
                "low",
                {"action": "Review and customize CODEOWNERS file"}
            )
        
        return "\n".join(lines)
    
    def _add_gap(
        self,
        gap_type: str,
        message: str,
        severity: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """Add a conversion gap"""
        self.gaps.append({
            "type": f"protection_{gap_type}",
            "message": message,
            "severity": severity,
            "context": context or {}
        })
    
    def get_required_status_checks_from_ci(
        self, 
        gitlab_ci_config: Dict[str, Any]
    ) -> List[str]:
        """
        Extract job names from GitLab CI config for required status checks.
        
        Args:
            gitlab_ci_config: Parsed GitLab CI YAML configuration
            
        Returns:
            List of job names to use as required status checks
        """
        job_names = []
        
        # Skip special keys
        skip_keys = {
            "stages", "variables", "workflow", "include", "default",
            "image", "services", "before_script", "after_script", "cache"
        }
        
        for key, value in gitlab_ci_config.items():
            # Skip hidden jobs (templates)
            if key.startswith("."):
                continue
            if key in skip_keys:
                continue
            if isinstance(value, dict) and ("script" in value or "trigger" in value):
                job_names.append(key)
        
        return job_names
