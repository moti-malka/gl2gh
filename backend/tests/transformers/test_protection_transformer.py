"""Tests for branch protection rules transformer"""

import pytest
from app.utils.transformers import ProtectionRulesTransformer


class TestProtectionRulesTransformer:
    """Test cases for GitLab to GitHub branch protection transformation"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.transformer = ProtectionRulesTransformer()
    
    def test_basic_branch_protection(self):
        """Test basic branch protection transformation"""
        protected_branches = [
            {
                "name": "main",
                "push_access_levels": [{"access_level": 40}],
                "merge_access_levels": [{"access_level": 40}],
                "allow_force_push": False
            }
        ]
        
        result = self.transformer.transform({
            "protected_branches": protected_branches
        })
        
        assert result.success
        assert "branch_protections" in result.data
        protections = result.data["branch_protections"]
        assert len(protections) == 1
        
        protection = protections[0]
        assert protection["branch"] == "main"
        assert protection["allow_force_pushes"] is False
        assert protection["allow_deletions"] is False
        assert protection["required_pull_request_reviews"] is not None
    
    def test_force_push_allowed(self):
        """Test force push allowed setting"""
        protected_branches = [
            {
                "name": "develop",
                "push_access_levels": [{"access_level": 30}],
                "merge_access_levels": [{"access_level": 30}],
                "allow_force_push": True
            }
        ]
        
        result = self.transformer.transform({
            "protected_branches": protected_branches
        })
        
        assert result.success
        protections = result.data["branch_protections"]
        protection = protections[0]
        assert protection["allow_force_pushes"] is True
    
    def test_code_owner_approval_required(self):
        """Test code owner approval requirement"""
        protected_branches = [
            {
                "name": "main",
                "push_access_levels": [{"access_level": 40}],
                "merge_access_levels": [{"access_level": 40}],
                "code_owner_approval_required": True,
                "allow_force_push": False
            }
        ]
        
        result = self.transformer.transform({
            "protected_branches": protected_branches
        })
        
        assert result.success
        protections = result.data["branch_protections"]
        protection = protections[0]
        reviews = protection["required_pull_request_reviews"]
        assert reviews is not None
        assert reviews["require_code_owner_reviews"] is True
    
    def test_approvals_before_merge(self):
        """Test approval count mapping"""
        protected_branches = [
            {
                "name": "main",
                "push_access_levels": [{"access_level": 40}],
                "merge_access_levels": [{"access_level": 40}],
                "approvals_before_merge": 2,
                "allow_force_push": False
            }
        ]
        
        result = self.transformer.transform({
            "protected_branches": protected_branches
        })
        
        assert result.success
        protections = result.data["branch_protections"]
        protection = protections[0]
        reviews = protection["required_pull_request_reviews"]
        assert reviews is not None
        assert reviews["required_approving_review_count"] == 2
    
    def test_ci_jobs_to_status_checks(self):
        """Test CI jobs mapping to required status checks"""
        protected_branches = [
            {
                "name": "main",
                "push_access_levels": [{"access_level": 40}],
                "merge_access_levels": [{"access_level": 40}],
                "allow_force_push": False
            }
        ]
        
        ci_jobs = ["build", "test", "lint"]
        
        result = self.transformer.transform({
            "protected_branches": protected_branches,
            "ci_jobs": ci_jobs
        })
        
        assert result.success
        protections = result.data["branch_protections"]
        protection = protections[0]
        status_checks = protection["required_status_checks"]
        assert status_checks is not None
        assert status_checks["strict"] is True
        assert set(status_checks["contexts"]) == set(ci_jobs)
    
    def test_multiple_branches(self):
        """Test multiple protected branches"""
        protected_branches = [
            {
                "name": "main",
                "push_access_levels": [{"access_level": 40}],
                "merge_access_levels": [{"access_level": 40}],
                "allow_force_push": False
            },
            {
                "name": "develop",
                "push_access_levels": [{"access_level": 30}],
                "merge_access_levels": [{"access_level": 30}],
                "allow_force_push": True
            }
        ]
        
        result = self.transformer.transform({
            "protected_branches": protected_branches
        })
        
        assert result.success
        protections = result.data["branch_protections"]
        assert len(protections) == 2
        
        branch_names = {p["branch"] for p in protections}
        assert branch_names == {"main", "develop"}
    
    def test_protected_tags(self):
        """Test protected tags transformation"""
        protected_tags = [
            {"name": "v*"},
            {"name": "release-*"}
        ]
        
        result = self.transformer.transform({
            "protected_branches": [],
            "protected_tags": protected_tags
        })
        
        assert result.success
        tag_protections = result.data["protected_tags"]
        assert len(tag_protections) == 2
        assert tag_protections[0]["pattern"] == "v*"
        assert tag_protections[1]["pattern"] == "release-*"
    
    def test_codeowners_generation_basic(self):
        """Test basic CODEOWNERS file generation"""
        approval_rules = [
            {
                "name": "Backend Approval",
                "eligible_approvers": [
                    {"id": 1, "username": "alice"},
                    {"id": 2, "username": "bob"}
                ],
                "groups": [],
                "file_pattern": "*.py"
            }
        ]
        
        project_members = [
            {"id": 1, "username": "alice"},
            {"id": 2, "username": "bob"}
        ]
        
        result = self.transformer.transform({
            "protected_branches": [],
            "approval_rules": approval_rules,
            "project_members": project_members
        })
        
        assert result.success
        codeowners = result.data["codeowners_content"]
        assert codeowners is not None
        assert "# CODEOWNERS" in codeowners
        assert "*.py" in codeowners
        assert "@alice" in codeowners
        assert "@bob" in codeowners
    
    def test_codeowners_generation_with_groups(self):
        """Test CODEOWNERS generation with groups/teams"""
        approval_rules = [
            {
                "name": "Frontend Approval",
                "eligible_approvers": [],
                "groups": [
                    {"path": "frontend-team", "name": "Frontend Team"}
                ],
                "file_pattern": "*.js"
            }
        ]
        
        result = self.transformer.transform({
            "protected_branches": [],
            "approval_rules": approval_rules,
            "project_members": []
        })
        
        assert result.success
        codeowners = result.data["codeowners_content"]
        assert codeowners is not None
        assert "*.js" in codeowners
        assert "@org/frontend-team" in codeowners
    
    def test_codeowners_generation_no_rules(self):
        """Test CODEOWNERS generation with no approval rules"""
        result = self.transformer.transform({
            "protected_branches": [],
            "approval_rules": [],
            "project_members": []
        })
        
        assert result.success
        codeowners = result.data["codeowners_content"]
        assert codeowners is not None
        # Should have default rule
        assert "* @org/maintainers" in codeowners
    
    def test_restricted_push_access_gap(self):
        """Test gap detection for restricted push access"""
        protected_branches = [
            {
                "name": "main",
                "push_access_levels": [
                    {"user_id": 123, "access_level": 40}
                ],
                "merge_access_levels": [{"access_level": 40}],
                "allow_force_push": False
            }
        ]
        
        result = self.transformer.transform({
            "protected_branches": protected_branches
        })
        
        assert result.success
        gaps = result.data["gaps"]
        # Should have gap for push restrictions
        push_gap = next((g for g in gaps if "push_restrictions" in g["type"]), None)
        assert push_gap is not None
        assert push_gap["severity"] == "high"
    
    def test_unprotect_access_level_gap(self):
        """Test gap detection for unprotect access level"""
        protected_branches = [
            {
                "name": "main",
                "push_access_levels": [{"access_level": 40}],
                "merge_access_levels": [{"access_level": 40}],
                "unprotect_access_level": 60,
                "allow_force_push": False
            }
        ]
        
        result = self.transformer.transform({
            "protected_branches": protected_branches
        })
        
        assert result.success
        gaps = result.data["gaps"]
        # Should have gap for unprotect access level
        unprotect_gap = next((g for g in gaps if "unprotect" in g["type"]), None)
        assert unprotect_gap is not None
    
    def test_tag_protection_gap(self):
        """Test gap detection for tag protection"""
        protected_tags = [{"name": "v1.0"}]
        
        result = self.transformer.transform({
            "protected_branches": [],
            "protected_tags": protected_tags
        })
        
        assert result.success
        gaps = result.data["gaps"]
        # Should have gap for tag protection
        tag_gap = next((g for g in gaps if "tag_protection" in g["type"]), None)
        assert tag_gap is not None
        assert "Pro/Enterprise" in tag_gap["message"]
    
    def test_get_required_status_checks_from_ci(self):
        """Test extracting job names from GitLab CI config"""
        gitlab_ci_config = {
            "stages": ["build", "test"],
            "variables": {"VAR": "value"},
            "build_job": {
                "stage": "build",
                "script": ["make build"]
            },
            "test_job": {
                "stage": "test",
                "script": ["make test"]
            },
            ".hidden_job": {
                "script": ["echo hidden"]
            }
        }
        
        job_names = self.transformer.get_required_status_checks_from_ci(gitlab_ci_config)
        
        assert "build_job" in job_names
        assert "test_job" in job_names
        assert ".hidden_job" not in job_names
        assert "stages" not in job_names
        assert "variables" not in job_names
    
    def test_metadata_tracking(self):
        """Test that metadata is properly tracked"""
        protected_branches = [
            {"name": "main", "push_access_levels": [], "merge_access_levels": [], "allow_force_push": False},
            {"name": "develop", "push_access_levels": [], "merge_access_levels": [], "allow_force_push": False}
        ]
        protected_tags = [{"name": "v*"}]
        
        result = self.transformer.transform({
            "protected_branches": protected_branches,
            "protected_tags": protected_tags
        })
        
        assert result.success
        assert result.metadata["branches_protected"] == 2
        assert result.metadata["tags_protected"] == 1
        assert "conversion_gaps" in result.metadata
    
    def test_empty_input(self):
        """Test handling of empty protected branches"""
        result = self.transformer.transform({
            "protected_branches": []
        })
        
        assert result.success
        assert result.data["branch_protections"] == []
        assert result.metadata["branches_protected"] == 0
    
    def test_missing_required_field(self):
        """Test validation of required fields"""
        result = self.transformer.transform({
            "protected_tags": []  # Missing protected_branches
        })
        
        assert not result.success
        assert len(result.errors) > 0
        assert "protected_branches" in result.errors[0]["message"]
