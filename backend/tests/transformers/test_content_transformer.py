"""Tests for content transformer"""

import pytest
from app.utils.transformers import ContentTransformer


class TestContentTransformer:
    """Test cases for issue and MR transformation"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.transformer = ContentTransformer()
        
        # Set up user mappings
        self.transformer.set_user_mappings([
            {
                "gitlab": {"username": "johndoe"},
                "github": {"login": "johndoe-gh"}
            },
            {
                "gitlab": {"username": "janedoe"},
                "github": {"login": "janed"}
            }
        ])
    
    def test_issue_transformation_basic(self):
        """Test basic issue transformation"""
        issue = {
            "id": 123,
            "iid": 45,
            "title": "Fix bug in login",
            "description": "The login page has a bug",
            "author": {"username": "johndoe", "name": "John Doe"},
            "created_at": "2024-01-15T10:00:00Z",
            "updated_at": "2024-01-15T12:00:00Z",
            "labels": ["bug", "high-priority"],
            "assignees": [{"username": "janedoe"}],
            "state": "opened",
            "web_url": "https://gitlab.com/project/issues/45"
        }
        
        result = self.transformer.transform({
            "content_type": "issue",
            "content": issue,
            "gitlab_project": "myorg/myproject",
            "github_repo": "myorg/myrepo"
        })
        
        assert result.success
        transformed = result.data
        
        assert transformed["title"] == "Fix bug in login"
        assert "Originally created as issue by @johndoe" in transformed["body"]
        assert transformed["labels"] == ["bug", "high-priority"]
        assert "johndoe-gh" in transformed["assignees"] or "janed" in transformed["assignees"]
        assert transformed["state"] == "open"
    
    def test_merge_request_transformation(self):
        """Test merge request to PR transformation"""
        mr = {
            "id": 456,
            "iid": 12,
            "title": "Add new feature",
            "description": "This MR adds a new feature",
            "author": {"username": "janedoe", "name": "Jane Doe"},
            "created_at": "2024-01-20T10:00:00Z",
            "updated_at": "2024-01-20T12:00:00Z",
            "source_branch": "feature-branch",
            "target_branch": "main",
            "labels": ["enhancement"],
            "assignees": [{"username": "johndoe"}],
            "reviewers": [{"username": "janedoe"}],
            "state": "opened",
            "work_in_progress": False,
            "web_url": "https://gitlab.com/project/merge_requests/12"
        }
        
        result = self.transformer.transform({
            "content_type": "merge_request",
            "content": mr,
            "gitlab_project": "myorg/myproject",
            "github_repo": "myorg/myrepo"
        })
        
        assert result.success
        transformed = result.data
        
        assert transformed["title"] == "Add new feature"
        assert "Originally created as merge request by @janedoe" in transformed["body"]
        assert transformed["head"] == "feature-branch"
        assert transformed["base"] == "main"
        assert transformed["draft"] is False
        assert transformed["state"] == "open"
    
    def test_mention_transformation(self):
        """Test @mention transformation"""
        issue = {
            "title": "Test",
            "description": "Hey @johndoe, can you review this? Also cc @janedoe",
            "author": {"username": "someone"},
            "state": "opened"
        }
        
        result = self.transformer.transform({
            "content_type": "issue",
            "content": issue,
            "gitlab_project": "",
            "github_repo": ""
        })
        
        assert result.success
        body = result.data["body"]
        
        # Mentions should be transformed
        assert "@johndoe-gh" in body
        assert "@janed" in body
    
    def test_cross_reference_transformation(self):
        """Test issue cross-reference transformation"""
        issue = {
            "title": "Test",
            "description": "This is related to #123 and !45",
            "author": {"username": "someone"},
            "state": "opened"
        }
        
        result = self.transformer.transform({
            "content_type": "issue",
            "content": issue,
            "gitlab_project": "myorg/myproject",
            "github_repo": "myorg/myrepo"
        })
        
        assert result.success
        body = result.data["body"]
        
        # Issue reference should be qualified
        assert "myorg/myrepo#123" in body
        # MR reference (!) should become # in GitHub
        assert "#45" in body or "myorg/myrepo#45" in body
    
    def test_label_sanitization(self):
        """Test label sanitization"""
        issue = {
            "title": "Test",
            "description": "Test",
            "author": {"username": "someone"},
            "labels": ["bug", "high priority!", "needs:review"],
            "state": "opened"
        }
        
        result = self.transformer.transform({
            "content_type": "issue",
            "content": issue,
            "gitlab_project": "",
            "github_repo": ""
        })
        
        assert result.success
        labels = result.data["labels"]
        
        # Labels should be sanitized
        assert "bug" in labels
        # Special characters should be removed/handled
        for label in labels:
            assert len(label) <= 50  # Length limit
    
    def test_comment_transformation(self):
        """Test comment transformation"""
        comment = {
            "id": 789,
            "body": "This looks good! @johndoe please merge",
            "author": {"username": "janedoe", "name": "Jane Doe"},
            "created_at": "2024-01-15T14:00:00Z",
            "updated_at": "2024-01-15T14:05:00Z"
        }
        
        transformed = self.transformer.transform_comment(
            comment,
            "myorg/myproject",
            "myorg/myrepo"
        )
        
        assert "Originally posted by @janedoe" in transformed["body"]
        assert "@johndoe-gh" in transformed["body"]  # Mention should be transformed
        assert transformed["metadata"]["gitlab_id"] == 789
    
    def test_milestone_transformation(self):
        """Test milestone transformation"""
        issue = {
            "title": "Test",
            "description": "Test",
            "author": {"username": "someone"},
            "milestone": {
                "id": 10,
                "title": "v1.0",
                "description": "First release"
            },
            "state": "opened"
        }
        
        result = self.transformer.transform({
            "content_type": "issue",
            "content": issue,
            "gitlab_project": "",
            "github_repo": ""
        })
        
        assert result.success
        assert result.data["milestone"] == "v1.0"
    
    def test_mr_state_mapping(self):
        """Test MR state to PR state mapping"""
        states = [
            ("opened", "open"),
            ("closed", "closed"),
            ("merged", "closed"),
            ("locked", "closed")
        ]
        
        for gitlab_state, expected_gh_state in states:
            mr = {
                "title": "Test",
                "description": "Test",
                "author": {"username": "someone"},
                "source_branch": "feature",
                "target_branch": "main",
                "state": gitlab_state
            }
            
            result = self.transformer.transform({
                "content_type": "merge_request",
                "content": mr,
                "gitlab_project": "",
                "github_repo": ""
            })
            
            assert result.success
            assert result.data["state"] == expected_gh_state
    
    def test_attribution_with_original_url(self):
        """Test attribution includes original URL"""
        issue = {
            "title": "Test",
            "description": "Test",
            "author": {"username": "johndoe", "name": "John Doe"},
            "created_at": "2024-01-15T10:00:00Z",
            "state": "opened",
            "web_url": "https://gitlab.com/project/issues/123"
        }
        
        result = self.transformer.transform({
            "content_type": "issue",
            "content": issue,
            "gitlab_project": "",
            "github_repo": ""
        })
        
        assert result.success
        body = result.data["body"]
        
        assert "https://gitlab.com/project/issues/123" in body
        assert "Original URL:" in body
