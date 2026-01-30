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
    
    @pytest.mark.asyncio
    async def test_push_lfs_no_objects(self, tmp_path):
        """Test LFS push when no objects exist"""
        from app.agents.actions.repository import PushLFSAction
        
        mock_github = Mock()
        lfs_path = tmp_path / "lfs"
        
        action_config = {
            "id": "action-003",
            "type": "lfs_configure",
            "parameters": {
                "lfs_objects_path": str(lfs_path),
                "target_repo": "org/test-repo"
            }
        }
        
        action = PushLFSAction(action_config, mock_github, {})
        result = await action.execute()
        
        assert result.success is True
        assert result.outputs["skipped"] is True
        assert "No LFS objects found" in result.outputs["reason"]
    
    @pytest.mark.asyncio
    async def test_push_lfs_success(self, tmp_path):
        """Test successful LFS push"""
        from app.agents.actions.repository import PushLFSAction
        
        # Setup
        mock_github = Mock()
        mock_repo = Mock()
        mock_repo.clone_url = "https://github.com/org/test-repo.git"
        mock_github.get_repo.return_value = mock_repo
        
        # Create LFS directory with manifest
        lfs_path = tmp_path / "lfs"
        lfs_path.mkdir(parents=True)
        
        manifest = {
            "total_count": 2,
            "total_size": 3072,
            "objects": [
                {"oid": "abc123", "path": "file1.bin", "size": 1024},
                {"oid": "def456", "path": "file2.bin", "size": 2048}
            ]
        }
        
        manifest_path = lfs_path / "manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)
        
        # Create mock LFS objects directory
        lfs_objects = lfs_path / "objects"
        lfs_objects.mkdir(parents=True)
        (lfs_objects / "test.bin").write_text("mock content")
        
        action_config = {
            "id": "action-003",
            "type": "lfs_configure",
            "parameters": {
                "lfs_objects_path": str(lfs_path),
                "target_repo": "org/test-repo"
            }
        }
        
        context = {"github_token": "ghp_test123"}
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            
            action = PushLFSAction(action_config, mock_github, context)
            result = await action.execute()
            
            assert result.success is True
            assert result.outputs["lfs_configured"] is True
            assert result.outputs["objects_pushed"] == 2
            assert result.outputs["total_size"] == 3072
    
    @pytest.mark.asyncio
    async def test_push_lfs_quota_error(self, tmp_path):
        """Test LFS push with quota error"""
        from app.agents.actions.repository import PushLFSAction
        import subprocess
        
        # Setup
        mock_github = Mock()
        mock_repo = Mock()
        mock_repo.clone_url = "https://github.com/org/test-repo.git"
        mock_github.get_repo.return_value = mock_repo
        
        # Create LFS directory with manifest
        lfs_path = tmp_path / "lfs"
        lfs_path.mkdir(parents=True)
        
        manifest = {
            "total_count": 1,
            "total_size": 1024,
            "objects": [{"oid": "abc123", "path": "file1.bin", "size": 1024}]
        }
        
        with open(lfs_path / "manifest.json", 'w') as f:
            json.dump(manifest, f)
        
        (lfs_path / "objects").mkdir(parents=True)
        
        action_config = {
            "id": "action-003",
            "type": "lfs_configure",
            "parameters": {
                "lfs_objects_path": str(lfs_path),
                "target_repo": "org/test-repo"
            }
        }
        
        context = {"github_token": "ghp_test123"}
        
        with patch('subprocess.run') as mock_run:
            # Clone and install succeed, push fails with quota error
            mock_run.side_effect = [
                Mock(returncode=0, stdout="", stderr=""),  # clone
                Mock(returncode=0, stdout="", stderr=""),  # lfs install
                subprocess.CalledProcessError(1, ['git', 'lfs', 'push'], 
                                             stderr="Error: quota exceeded")  # push
            ]
            
            action = PushLFSAction(action_config, mock_github, context)
            result = await action.execute()
            
            assert result.success is False
            assert "quota" in result.error.lower()


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
