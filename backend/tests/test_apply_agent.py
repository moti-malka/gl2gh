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


class TestPackageActions:
    """Test package-related actions"""
    
    @pytest.mark.asyncio
    async def test_publish_npm_package(self):
        """Test npm package publishing action"""
        from app.agents.actions.packages import PublishPackageAction
        
        action_config = {
            "id": "action-pkg-001",
            "type": "package_publish",
            "parameters": {
                "target_repo": "org/repo",
                "package_type": "npm",
                "package_name": "test-package",
                "version": "1.0.0",
                "files": [
                    {
                        "file_name": "test-package-1.0.0.tgz",
                        "size": 1024,
                        "local_path": "packages/npm/test-package/1.0.0/test-package-1.0.0.tgz"
                    }
                ]
            }
        }
        
        github_client = Mock()
        context = {}
        
        action = PublishPackageAction(action_config, github_client, context)
        result = await action.execute()
        
        assert result.success is True
        assert result.outputs["package_name"] == "test-package"
        assert result.outputs["version"] == "1.0.0"
        assert result.outputs["package_type"] == "npm"
        assert result.outputs["status"] in ["published", "published"]  # Should provide manual steps
        assert "details" in result.outputs
    
    @pytest.mark.asyncio
    async def test_publish_maven_package(self):
        """Test Maven package publishing action"""
        from app.agents.actions.packages import PublishPackageAction
        
        action_config = {
            "id": "action-pkg-002",
            "type": "package_publish",
            "parameters": {
                "target_repo": "org/repo",
                "package_type": "maven",
                "package_name": "maven-lib",
                "version": "2.0.0",
                "files": [
                    {
                        "file_name": "maven-lib-2.0.0.jar",
                        "size": 2048,
                        "local_path": "packages/maven/maven-lib/2.0.0/maven-lib-2.0.0.jar"
                    },
                    {
                        "file_name": "maven-lib-2.0.0.pom",
                        "size": 512,
                        "local_path": "packages/maven/maven-lib/2.0.0/maven-lib-2.0.0.pom"
                    }
                ]
            }
        }
        
        github_client = Mock()
        context = {}
        
        action = PublishPackageAction(action_config, github_client, context)
        result = await action.execute()
        
        assert result.success is True
        assert result.outputs["package_name"] == "maven-lib"
        assert result.outputs["version"] == "2.0.0"
        assert result.outputs["package_type"] == "maven"
    
    @pytest.mark.asyncio
    async def test_publish_unsupported_package(self):
        """Test unsupported package type handling"""
        from app.agents.actions.packages import PublishPackageAction
        
        action_config = {
            "id": "action-pkg-003",
            "type": "package_publish",
            "parameters": {
                "target_repo": "org/repo",
                "package_type": "pypi",  # Unsupported
                "package_name": "python-lib",
                "version": "1.0.0",
                "files": [
                    {
                        "file_name": "python-lib-1.0.0.whl",
                        "size": 3072,
                        "local_path": "packages/pypi/python-lib/1.0.0/python-lib-1.0.0.whl"
                    }
                ]
            }
        }
        
        github_client = Mock()
        context = {}
        
        action = PublishPackageAction(action_config, github_client, context)
        result = await action.execute()
        
        assert result.success is True  # Still succeeds but marks as unsupported
        assert result.outputs["package_name"] == "python-lib"
        assert result.outputs["package_type"] == "pypi"
        assert result.outputs["status"] == "unsupported"
        assert "manual migration" in result.outputs["note"].lower()
    
    @pytest.mark.asyncio
    async def test_publish_package_without_files(self):
        """Test package without files"""
        from app.agents.actions.packages import PublishPackageAction
        
        action_config = {
            "id": "action-pkg-004",
            "type": "package_publish",
            "parameters": {
                "target_repo": "org/repo",
                "package_type": "npm",
                "package_name": "missing-package",
                "version": "1.0.0",
                "files": []  # No files
            }
        }
        
        github_client = Mock()
        context = {}
        
        action = PublishPackageAction(action_config, github_client, context)
        result = await action.execute()
        
        assert result.success is True
        assert result.outputs["status"] == "no_files"
        assert "manual" in result.outputs["note"].lower()
    
    @pytest.mark.asyncio
    async def test_publish_nuget_package(self):
        """Test NuGet package publishing action"""
        from app.agents.actions.packages import PublishPackageAction
        
        action_config = {
            "id": "action-pkg-005",
            "type": "package_publish",
            "parameters": {
                "target_repo": "org/repo",
                "package_type": "nuget",
                "package_name": "NugetLib",
                "version": "3.0.0",
                "files": [
                    {
                        "file_name": "NugetLib.3.0.0.nupkg",
                        "size": 4096,
                        "local_path": "packages/nuget/NugetLib/3.0.0/NugetLib.3.0.0.nupkg"
                    }
                ]
            }
        }
        
        github_client = Mock()
        context = {}
        
        action = PublishPackageAction(action_config, github_client, context)
        result = await action.execute()
        
        assert result.success is True
        assert result.outputs["package_name"] == "NugetLib"
        assert result.outputs["version"] == "3.0.0"
        assert result.outputs["package_type"] == "nuget"
        assert "details" in result.outputs
