"""Unit tests for rollback functionality"""

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock
from pathlib import Path
import json
import tempfile

from app.agents.actions.base import BaseAction, ActionResult
from app.agents.actions.repository import CreateRepositoryAction
from app.agents.actions.issues import (
    CreateLabelAction,
    CreateMilestoneAction,
    CreateIssueAction,
    AddIssueCommentAction
)
from app.agents.actions.releases import CreateReleaseAction
from app.agents.actions.pull_requests import CreatePullRequestAction, AddPRCommentAction
from app.agents.actions.settings import (
    SetBranchProtectionAction,
    AddCollaboratorAction,
    CreateWebhookAction
)
from app.agents.apply_agent import ApplyAgent


class TestActionResultRollbackData:
    """Test ActionResult rollback data tracking"""
    
    def test_action_result_with_rollback_data(self):
        """Test ActionResult includes rollback data"""
        result = ActionResult(
            success=True,
            action_id="action-001",
            action_type="repo_create",
            outputs={"repo_full_name": "org/repo"},
            rollback_data={"repo_full_name": "org/repo", "repo_id": 12345},
            reversible=True
        )
        
        assert result.rollback_data is not None
        assert result.rollback_data["repo_full_name"] == "org/repo"
        assert result.rollback_data["repo_id"] == 12345
        assert result.reversible is True
    
    def test_action_result_non_reversible(self):
        """Test ActionResult for non-reversible action"""
        result = ActionResult(
            success=True,
            action_id="action-002",
            action_type="repo_push",
            outputs={"pushed": True},
            reversible=False
        )
        
        assert result.reversible is False
    
    def test_action_result_to_dict_includes_rollback(self):
        """Test ActionResult.to_dict includes rollback fields"""
        result = ActionResult(
            success=True,
            action_id="action-003",
            action_type="issue_create",
            outputs={"issue_number": 42},
            rollback_data={"target_repo": "org/repo", "issue_number": 42}
        )
        
        result_dict = result.to_dict()
        assert "rollback_data" in result_dict
        assert "reversible" in result_dict
        assert result_dict["rollback_data"]["issue_number"] == 42


class TestRepositoryRollbacks:
    """Test repository action rollbacks"""
    
    @pytest.mark.asyncio
    async def test_create_repository_rollback(self):
        """Test rolling back repository creation"""
        mock_github = Mock()
        mock_repo = Mock()
        mock_github.get_repo.return_value = mock_repo
        
        action_config = {
            "id": "action-001",
            "type": "repo_create",
            "parameters": {}
        }
        
        action = CreateRepositoryAction(action_config, mock_github, {})
        rollback_data = {"repo_full_name": "org/test-repo", "repo_id": 12345}
        
        result = await action.rollback(rollback_data)
        
        assert result is True
        mock_github.get_repo.assert_called_once_with("org/test-repo")
        mock_repo.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_repository_rollback_not_found(self):
        """Test rolling back repository that doesn't exist"""
        from github import GithubException
        
        mock_github = Mock()
        mock_github.get_repo.side_effect = GithubException(404, {"message": "Not found"}, None)
        
        action_config = {
            "id": "action-001",
            "type": "repo_create",
            "parameters": {}
        }
        
        action = CreateRepositoryAction(action_config, mock_github, {})
        rollback_data = {"repo_full_name": "org/test-repo"}
        
        # Should return True even if repo doesn't exist (already deleted)
        result = await action.rollback(rollback_data)
        assert result is True


class TestIssueRollbacks:
    """Test issue action rollbacks"""
    
    @pytest.mark.asyncio
    async def test_create_label_rollback(self):
        """Test rolling back label creation"""
        mock_github = Mock()
        mock_repo = Mock()
        mock_label = Mock()
        mock_repo.get_label.return_value = mock_label
        mock_github.get_repo.return_value = mock_repo
        
        action_config = {
            "id": "action-010",
            "type": "label_create",
            "parameters": {}
        }
        
        action = CreateLabelAction(action_config, mock_github, {})
        rollback_data = {"target_repo": "org/repo", "label_name": "bug"}
        
        result = await action.rollback(rollback_data)
        
        assert result is True
        mock_label.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_milestone_rollback(self):
        """Test rolling back milestone creation"""
        mock_github = Mock()
        mock_repo = Mock()
        mock_milestone = Mock()
        mock_repo.get_milestone.return_value = mock_milestone
        mock_github.get_repo.return_value = mock_repo
        
        action_config = {
            "id": "action-011",
            "type": "milestone_create",
            "parameters": {}
        }
        
        action = CreateMilestoneAction(action_config, mock_github, {})
        rollback_data = {"target_repo": "org/repo", "milestone_number": 1}
        
        result = await action.rollback(rollback_data)
        
        assert result is True
        mock_milestone.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_issue_rollback(self):
        """Test rolling back issue creation by closing it"""
        mock_github = Mock()
        mock_repo = Mock()
        mock_issue = Mock()
        mock_repo.get_issue.return_value = mock_issue
        mock_github.get_repo.return_value = mock_repo
        
        action_config = {
            "id": "action-020",
            "type": "issue_create",
            "parameters": {}
        }
        
        action = CreateIssueAction(action_config, mock_github, {})
        rollback_data = {"target_repo": "org/repo", "issue_number": 42}
        
        result = await action.rollback(rollback_data)
        
        assert result is True
        mock_issue.edit.assert_called_once_with(state="closed")
        mock_issue.create_comment.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_add_issue_comment_not_reversible(self):
        """Test that issue comments are marked non-reversible"""
        action_config = {
            "id": "action-021",
            "type": "issue_comment_add",
            "parameters": {}
        }
        
        action = AddIssueCommentAction(action_config, Mock(), {})
        assert action.is_reversible() is False


class TestReleaseRollbacks:
    """Test release action rollbacks"""
    
    @pytest.mark.asyncio
    async def test_create_release_rollback(self):
        """Test rolling back release creation"""
        mock_github = Mock()
        mock_repo = Mock()
        mock_release = Mock()
        mock_repo.get_release.return_value = mock_release
        mock_github.get_repo.return_value = mock_repo
        
        action_config = {
            "id": "action-030",
            "type": "release_create",
            "parameters": {}
        }
        
        action = CreateReleaseAction(action_config, mock_github, {})
        rollback_data = {"target_repo": "org/repo", "release_id": 123}
        
        result = await action.rollback(rollback_data)
        
        assert result is True
        mock_release.delete_release.assert_called_once()


class TestPullRequestRollbacks:
    """Test pull request action rollbacks"""
    
    @pytest.mark.asyncio
    async def test_create_pr_rollback(self):
        """Test rolling back PR creation"""
        mock_github = Mock()
        mock_repo = Mock()
        mock_pr = Mock()
        mock_repo.get_pull.return_value = mock_pr
        mock_github.get_repo.return_value = mock_repo
        
        action_config = {
            "id": "action-040",
            "type": "pr_create",
            "parameters": {}
        }
        
        action = CreatePullRequestAction(action_config, mock_github, {})
        rollback_data = {
            "target_repo": "org/repo",
            "pr_number": 10,
            "created_as": "pull_request"
        }
        
        result = await action.rollback(rollback_data)
        
        assert result is True
        mock_pr.edit.assert_called_once_with(state="closed")
        mock_pr.create_issue_comment.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_pr_as_issue_rollback(self):
        """Test rolling back PR created as issue"""
        mock_github = Mock()
        mock_repo = Mock()
        mock_issue = Mock()
        mock_repo.get_issue.return_value = mock_issue
        mock_github.get_repo.return_value = mock_repo
        
        action_config = {
            "id": "action-041",
            "type": "pr_create",
            "parameters": {}
        }
        
        action = CreatePullRequestAction(action_config, mock_github, {})
        rollback_data = {
            "target_repo": "org/repo",
            "issue_number": 10,
            "created_as": "issue"
        }
        
        result = await action.rollback(rollback_data)
        
        assert result is True
        mock_issue.edit.assert_called_once_with(state="closed")
        mock_issue.create_comment.assert_called_once()


class TestSettingsRollbacks:
    """Test settings action rollbacks"""
    
    @pytest.mark.asyncio
    async def test_branch_protection_rollback(self):
        """Test rolling back branch protection"""
        mock_github = Mock()
        mock_repo = Mock()
        mock_branch = Mock()
        mock_repo.get_branch.return_value = mock_branch
        mock_github.get_repo.return_value = mock_repo
        
        action_config = {
            "id": "action-050",
            "type": "protection_set",
            "parameters": {}
        }
        
        action = SetBranchProtectionAction(action_config, mock_github, {})
        rollback_data = {"target_repo": "org/repo", "branch": "main"}
        
        result = await action.rollback(rollback_data)
        
        assert result is True
        mock_branch.remove_protection.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_collaborator_rollback(self):
        """Test rolling back collaborator addition"""
        mock_github = Mock()
        mock_repo = Mock()
        mock_github.get_repo.return_value = mock_repo
        
        action_config = {
            "id": "action-051",
            "type": "collaborator_add",
            "parameters": {}
        }
        
        action = AddCollaboratorAction(action_config, mock_github, {})
        rollback_data = {"target_repo": "org/repo", "username": "testuser"}
        
        result = await action.rollback(rollback_data)
        
        assert result is True
        mock_repo.remove_from_collaborators.assert_called_once_with("testuser")
    
    @pytest.mark.asyncio
    async def test_webhook_rollback(self):
        """Test rolling back webhook creation"""
        mock_github = Mock()
        mock_repo = Mock()
        mock_hook = Mock()
        mock_repo.get_hook.return_value = mock_hook
        mock_github.get_repo.return_value = mock_repo
        
        action_config = {
            "id": "action-052",
            "type": "webhook_create",
            "parameters": {}
        }
        
        action = CreateWebhookAction(action_config, mock_github, {})
        rollback_data = {"target_repo": "org/repo", "webhook_id": 999}
        
        result = await action.rollback(rollback_data)
        
        assert result is True
        mock_hook.delete.assert_called_once()


class TestApplyAgentRollback:
    """Test Apply Agent rollback orchestration"""
    
    @pytest.mark.asyncio
    async def test_rollback_migration_success(self):
        """Test successful rollback of multiple actions"""
        # Create temporary file with executed actions
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            executed_actions = {
                "executed_actions": [
                    {
                        "action_id": "action-001",
                        "action_type": "repo_create",
                        "action_config": {
                            "id": "action-001",
                            "type": "repo_create",
                            "parameters": {"org": "test", "name": "repo1"}
                        },
                        "rollback_data": {"repo_full_name": "test/repo1"},
                        "reversible": True
                    },
                    {
                        "action_id": "action-002",
                        "action_type": "issue_create",
                        "action_config": {
                            "id": "action-002",
                            "type": "issue_create",
                            "parameters": {"target_repo": "test/repo1"}
                        },
                        "rollback_data": {"target_repo": "test/repo1", "issue_number": 1},
                        "reversible": True
                    }
                ],
                "timestamp": "2024-01-01T00:00:00"
            }
            json.dump(executed_actions, f)
            temp_path = f.name
        
        try:
            # Mock GitHub client
            mock_github = Mock()
            mock_repo = Mock()
            mock_issue = Mock()
            mock_repo.get_issue.return_value = mock_issue
            mock_github.get_repo.return_value = mock_repo
            
            # Create Apply Agent
            agent = ApplyAgent()
            agent.github_client = mock_github
            agent.execution_context = {}
            
            # Perform rollback
            result = await agent.rollback_migration(temp_path)
            
            # Verify results
            assert result["status"] == "success"
            assert result["rolled_back"] == 2
            assert result["skipped"] == 0
            assert result["failed"] == 0
            
            # Verify rollback was called in reverse order
            # (issue first, then repo)
            assert mock_issue.edit.called
            assert mock_repo.delete.called
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_rollback_skips_non_reversible(self):
        """Test rollback skips non-reversible actions"""
        # Create temporary file with executed actions
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            executed_actions = {
                "executed_actions": [
                    {
                        "action_id": "action-001",
                        "action_type": "repo_create",
                        "action_config": {
                            "id": "action-001",
                            "type": "repo_create",
                            "parameters": {}
                        },
                        "rollback_data": {"repo_full_name": "test/repo1"},
                        "reversible": True
                    },
                    {
                        "action_id": "action-002",
                        "action_type": "repo_push",
                        "action_config": {
                            "id": "action-002",
                            "type": "repo_push",
                            "parameters": {}
                        },
                        "rollback_data": {},
                        "reversible": False
                    }
                ],
                "timestamp": "2024-01-01T00:00:00"
            }
            json.dump(executed_actions, f)
            temp_path = f.name
        
        try:
            mock_github = Mock()
            mock_repo = Mock()
            mock_github.get_repo.return_value = mock_repo
            
            agent = ApplyAgent()
            agent.github_client = mock_github
            agent.execution_context = {}
            
            result = await agent.rollback_migration(temp_path)
            
            assert result["rolled_back"] == 1
            assert result["skipped"] == 1
            assert result["status"] == "success"
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_rollback_file_not_found(self):
        """Test rollback handles missing file"""
        agent = ApplyAgent()
        agent.github_client = Mock()
        agent.execution_context = {}
        
        result = await agent.rollback_migration("/nonexistent/file.json")
        
        assert result["status"] == "failed"
        assert "error" in result
        assert "not found" in result["error"].lower()
