"""Unit tests for Apply Agent action executors"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from pathlib import Path
import json

from app.agents.actions.base import BaseAction, ActionResult
from app.agents.actions.repository import (
    CreateRepositoryAction,
    PushCodeAction,
    ConfigureRepositoryAction
)
from app.agents.actions.issues import (
    CreateLabelAction,
    CreateMilestoneAction,
    CreateIssueAction,
    AddIssueCommentAction
)
from app.agents.actions.ci_cd import (
    CommitWorkflowAction,
    SetSecretAction
)


class TestBaseAction:
    """Test BaseAction functionality"""
    
    def test_idempotency_check(self):
        """Test idempotency checking"""
        action_config = {
            "id": "action-001",
            "type": "test_action",
            "idempotency_key": "test-key-001",
            "parameters": {}
        }
        context = {
            "executed_actions": {
                "test-key-001": ActionResult(
                    success=True,
                    action_id="action-001",
                    action_type="test_action",
                    outputs={"test": "value"}
                )
            }
        }
        
        # Create a concrete implementation for testing
        class TestAction(BaseAction):
            async def execute(self):
                return ActionResult(
                    success=True,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={}
                )
        
        action = TestAction(action_config, Mock(), context)
        result = action.check_idempotency()
        
        assert result is not None
        assert result.success is True
        assert result.outputs["test"] == "value"
    
    def test_action_result_simulation(self):
        """Test ActionResult with simulation metadata"""
        result = ActionResult(
            success=True,
            action_id="action-001",
            action_type="repo_create",
            outputs={"repo": "org/repo"},
            simulated=True,
            simulation_outcome="would_create",
            simulation_message="Would create repository 'org/repo'"
        )
        
        result_dict = result.to_dict()
        assert result_dict["simulated"] is True
        assert result_dict["simulation_outcome"] == "would_create"
        assert result_dict["simulation_message"] == "Would create repository 'org/repo'"
    
    def test_id_mapping(self):
        """Test ID mapping functionality"""
        action_config = {
            "id": "action-001",
            "type": "test_action",
            "parameters": {}
        }
        context = {}
        
        class TestAction(BaseAction):
            async def execute(self):
                return ActionResult(
                    success=True,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={}
                )
        
        action = TestAction(action_config, Mock(), context)
        
        # Set mapping
        action.set_id_mapping("issue", "123", 456)
        
        # Get mapping
        github_id = action.get_id_mapping("issue", "123")
        assert github_id == 456
        
        # Check context updated
        assert "id_mappings" in context
        assert "issue" in context["id_mappings"]
        assert context["id_mappings"]["issue"]["123"] == 456


class TestRepositoryActions:
    """Test repository-related actions"""
    
    @pytest.mark.asyncio
    async def test_create_repository_success(self):
        """Test successful repository creation"""
        mock_github = Mock()
        mock_org = Mock()
        mock_repo = Mock()
        mock_repo.full_name = "org/test-repo"
        mock_repo.html_url = "https://github.com/org/test-repo"
        mock_repo.id = 12345
        
        mock_org.create_repo.return_value = mock_repo
        mock_github.get_organization.return_value = mock_org
        
        action_config = {
            "id": "action-001",
            "type": "repo_create",
            "parameters": {
                "org": "org",
                "name": "test-repo",
                "description": "Test repository",
                "private": True
            }
        }
        
        action = CreateRepositoryAction(action_config, mock_github, {})
        result = await action.execute()
        
        assert result.success is True
        assert result.outputs["repo_full_name"] == "org/test-repo"
        assert result.outputs["repo_id"] == 12345
    
    @pytest.mark.asyncio
    async def test_create_repository_simulate_would_create(self):
        """Test simulating repository creation when repo doesn't exist"""
        from github import GithubException
        
        mock_github = Mock()
        # Simulate repo doesn't exist (404)
        mock_github.get_repo.side_effect = GithubException(404, {"message": "Not found"}, None)
        
        action_config = {
            "id": "action-001",
            "type": "repo_create",
            "parameters": {
                "org": "org",
                "name": "test-repo",
                "description": "Test repository",
                "private": True
            }
        }
        
        action = CreateRepositoryAction(action_config, mock_github, {})
        result = await action.simulate()
        
        assert result.success is True
        assert result.simulated is True
        assert result.simulation_outcome == "would_create"
        assert "Would create repository" in result.simulation_message
        assert result.outputs["repo_full_name"] == "org/test-repo"
    
    @pytest.mark.asyncio
    async def test_create_repository_simulate_would_skip(self):
        """Test simulating repository creation when repo already exists"""
        mock_github = Mock()
        mock_repo = Mock()
        mock_repo.full_name = "org/test-repo"
        # Simulate repo already exists
        mock_github.get_repo.return_value = mock_repo
        
        action_config = {
            "id": "action-001",
            "type": "repo_create",
            "parameters": {
                "org": "org",
                "name": "test-repo"
            }
        }
        
        action = CreateRepositoryAction(action_config, mock_github, {})
        result = await action.simulate()
        
        assert result.success is True
        assert result.simulated is True
        assert result.simulation_outcome == "would_skip"
        assert "already exists" in result.simulation_message
    
    @pytest.mark.asyncio
    async def test_create_repository_already_exists(self):
        """Test repository creation when repo already exists"""
        from github import GithubException
        
        mock_github = Mock()
        mock_org = Mock()
        mock_user = Mock()
        mock_repo = Mock()
        mock_repo.full_name = "org/test-repo"
        mock_repo.html_url = "https://github.com/org/test-repo"
        mock_repo.id = 12345
        
        # First call to org fails with 422
        exception = GithubException(422, {"message": "Repository already exists"}, None)
        mock_org.create_repo.side_effect = exception
        mock_github.get_organization.return_value = mock_org
        
        # Second call tries user and succeeds
        mock_user.create_repo.return_value = mock_repo
        mock_github.get_user.return_value = mock_user
        
        action_config = {
            "id": "action-001",
            "type": "repo_create",
            "parameters": {
                "org": "org",
                "name": "test-repo",
                "description": "Test repository",
                "private": True
            }
        }
        
        action = CreateRepositoryAction(action_config, mock_github, {})
        result = await action.execute()
        
        # Should succeed - tries user after org fails
        assert result.success is True


class TestIssueActions:
    """Test issue-related actions"""
    
    @pytest.mark.asyncio
    async def test_create_label_success(self):
        """Test successful label creation"""
        mock_github = Mock()
        mock_repo = Mock()
        mock_label = Mock()
        mock_label.id = 1
        mock_label.name = "bug"
        
        mock_repo.create_label.return_value = mock_label
        mock_github.get_repo.return_value = mock_repo
        
        action_config = {
            "id": "action-010",
            "type": "label_create",
            "parameters": {
                "target_repo": "org/repo",
                "name": "bug",
                "color": "d73a4a",
                "description": "Bug reports"
            }
        }
        
        action = CreateLabelAction(action_config, mock_github, {})
        result = await action.execute()
        
        assert result.success is True
        assert result.outputs["label_name"] == "bug"
        assert result.outputs["label_id"] == 1
    
    @pytest.mark.asyncio
    async def test_create_issue_with_mapping(self):
        """Test issue creation with ID mapping"""
        mock_github = Mock()
        mock_repo = Mock()
        mock_issue = Mock()
        mock_issue.number = 42
        mock_issue.html_url = "https://github.com/org/repo/issues/42"
        
        mock_repo.create_issue.return_value = mock_issue
        mock_github.get_repo.return_value = mock_repo
        
        context = {}
        action_config = {
            "id": "action-020",
            "type": "issue_create",
            "parameters": {
                "target_repo": "org/repo",
                "title": "Test Issue",
                "body": "Test body",
                "gitlab_issue_id": "123"
            }
        }
        
        action = CreateIssueAction(action_config, mock_github, context)
        result = await action.execute()
        
        assert result.success is True
        assert result.outputs["issue_number"] == 42
        assert result.outputs["gitlab_issue_id"] == "123"
        
        # Check ID mapping was stored
        assert "id_mappings" in context
        assert context["id_mappings"]["issue"]["123"] == 42
    
    @pytest.mark.asyncio
    async def test_add_comment_with_attribution(self):
        """Test adding comment with attribution"""
        mock_github = Mock()
        mock_repo = Mock()
        mock_issue = Mock()
        mock_comment = Mock()
        mock_comment.id = 999
        
        mock_issue.create_comment.return_value = mock_comment
        mock_repo.get_issue.return_value = mock_issue
        mock_github.get_repo.return_value = mock_repo
        
        context = {
            "id_mappings": {
                "issue": {"123": 42}
            }
        }
        
        action_config = {
            "id": "action-021",
            "type": "issue_comment_add",
            "parameters": {
                "target_repo": "org/repo",
                "gitlab_issue_id": "123",
                "body": "Test comment",
                "original_author": "olduser"
            }
        }
        
        action = AddIssueCommentAction(action_config, mock_github, context)
        result = await action.execute()
        
        assert result.success is True
        assert result.outputs["comment_id"] == 999
        
        # Check attribution was added
        call_args = mock_issue.create_comment.call_args[0][0]
        assert "olduser" in call_args
        assert "Test comment" in call_args


class TestCICDActions:
    """Test CI/CD-related actions"""
    
    @pytest.mark.asyncio
    async def test_commit_workflow_success(self):
        """Test committing workflow file"""
        mock_github = Mock()
        mock_repo = Mock()
        
        # Simulate file doesn't exist (404)
        from github import GithubException
        mock_repo.get_contents.side_effect = GithubException(404, {"message": "Not found"})
        mock_repo.create_file.return_value = {"commit": {"sha": "abc123"}}
        mock_github.get_repo.return_value = mock_repo
        
        # Create temporary workflow file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write("name: CI\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n")
            workflow_path = f.name
        
        try:
            action_config = {
                "id": "action-030",
                "type": "workflow_commit",
                "parameters": {
                    "workflow_path": workflow_path,
                    "target_path": ".github/workflows/ci.yml",
                    "target_repo": "org/repo",
                    "branch": "main",
                    "commit_message": "Add CI workflow"
                }
            }
            
            action = CommitWorkflowAction(action_config, mock_github, {})
            result = await action.execute()
            
            assert result.success is True
            assert result.outputs["action"] == "created"
            assert result.outputs["path"] == ".github/workflows/ci.yml"
        finally:
            Path(workflow_path).unlink(missing_ok=True)


class TestApplyAgent:
    """Test Apply Agent orchestration"""
    
    @pytest.mark.asyncio
    async def test_dependency_resolution(self):
        """Test action dependency resolution"""
        from app.agents.apply_agent import ApplyAgent
        
        agent = ApplyAgent()
        
        # Create mock results
        results = [
            ActionResult(success=True, action_id="action-001", action_type="repo_create", outputs={}),
            ActionResult(success=True, action_id="action-002", action_type="repo_push", outputs={}),
        ]
        
        # Test with satisfied dependencies
        assert agent._check_dependencies(["action-001"], results) is True
        assert agent._check_dependencies(["action-001", "action-002"], results) is True
        
        # Test with unsatisfied dependencies
        assert agent._check_dependencies(["action-003"], results) is False
        assert agent._check_dependencies(["action-001", "action-003"], results) is False
    
    @pytest.mark.asyncio
    async def test_validate_inputs(self):
        """Test input validation"""
        from app.agents.apply_agent import ApplyAgent
        
        agent = ApplyAgent()
        
        # Valid inputs
        valid_inputs = {
            "github_token": "ghp_test",
            "plan": {
                "actions": []
            },
            "output_dir": "/tmp/test"
        }
        assert agent.validate_inputs(valid_inputs) is True
        
        # Missing required field
        invalid_inputs = {
            "github_token": "ghp_test",
            "output_dir": "/tmp/test"
        }
        assert agent.validate_inputs(invalid_inputs) is False
        
        # Invalid plan structure
        invalid_plan = {
            "github_token": "ghp_test",
            "plan": "not a dict",
            "output_dir": "/tmp/test"
        }
        assert agent.validate_inputs(invalid_plan) is False
    
    @pytest.mark.asyncio
    async def test_dry_run_mode(self):
        """Test dry-run mode execution"""
        from app.agents.apply_agent import ApplyAgent
        from unittest.mock import Mock, patch
        from github import GithubException
        import tempfile
        import os
        
        agent = ApplyAgent()
        
        # Create temporary directory for output
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock GitHub client
            mock_github = Mock()
            # Simulate repo doesn't exist (404)
            mock_github.get_repo.side_effect = GithubException(404, {"message": "Not found"}, None)
            
            plan = {
                "actions": [
                    {
                        "id": "action-001",
                        "type": "repo_create",
                        "parameters": {
                            "org": "org",
                            "name": "repo",
                            "description": "Test repo"
                        }
                    }
                ],
                "summary": {
                    "total_actions": 1
                }
            }
            
            inputs = {
                "github_token": "ghp_test",
                "plan": plan,
                "output_dir": tmpdir,
                "dry_run": True
            }
            
            with patch.object(agent, 'github_client', mock_github):
                result = await agent.execute(inputs)
            
            # Verify dry-run was successful
            assert result["status"] in ["success", "partial", "failed"]
            assert result["outputs"]["dry_run"] is True
            
            # Verify dry-run report was created
            dry_run_report_path = os.path.join(tmpdir, "dry_run_report.json")
            assert os.path.exists(dry_run_report_path)
            
            # Verify ID mappings were NOT created (dry-run doesn't create them)
            id_mappings_path = os.path.join(tmpdir, "id_mappings.json")
            assert not os.path.exists(id_mappings_path)
