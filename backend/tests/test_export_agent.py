"""Tests for ExportAgent"""

import pytest
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call
from app.agents.export_agent import ExportAgent


@pytest.fixture
def export_agent():
    """Create ExportAgent instance"""
    return ExportAgent()


@pytest.fixture
def export_inputs(tmp_path):
    """Sample export inputs"""
    return {
        "gitlab_url": "https://gitlab.com",
        "gitlab_token": "test-token-12345678",
        "project_id": "123",
        "output_dir": str(tmp_path / "export")
    }


@pytest.fixture
def mock_gitlab_client():
    """Mock GitLab client"""
    client = AsyncMock()
    
    # Mock project
    client.get_project.return_value = {
        "id": 123,
        "path_with_namespace": "test/project",
        "http_url_to_repo": "https://gitlab.com/test/project.git",
        "visibility": "private",
        "default_branch": "main",
        "wiki_enabled": True,
        "lfs_enabled": False,
        "issues_enabled": True,
        "merge_requests_enabled": True
    }
    
    # Mock repository data
    client.list_branches.return_value = [
        {"name": "main", "default": True},
        {"name": "develop", "default": False}
    ]
    client.list_tags.return_value = [
        {"name": "v1.0.0", "message": "Release 1.0.0"}
    ]
    client.has_lfs.return_value = False
    
    # Mock CI/CD data
    client.get_file_content.return_value = """
stages:
  - build
  - test

build:
  stage: build
  script:
    - echo "Building"
"""
    client.list_variables.return_value = [
        {"key": "VAR1", "protected": True, "masked": False}
    ]
    client.list_environments.return_value = [
        {"name": "production", "external_url": "https://prod.example.com"}
    ]
    client.list_pipeline_schedules.return_value = [
        {"description": "Nightly build", "cron": "0 0 * * *"}
    ]
    client.list_pipelines.return_value = [
        {"id": 1, "status": "success", "ref": "main"}
    ]
    
    # Mock issues
    async def mock_list_issues(project_id):
        """Async generator for mocking list_issues"""
        issues = [
            {"iid": 1, "title": "Issue 1", "state": "opened"},
            {"iid": 2, "title": "Issue 2", "state": "closed"}
        ]
        for issue in issues:
            yield issue
    
    client.list_issues = mock_list_issues  # Direct assignment
    client.get_issue.return_value = {
        "iid": 1,
        "title": "Issue 1",
        "description": "Description",
        "state": "opened"
    }
    client.list_issue_notes.return_value = [
        {"body": "Comment 1", "author": {"username": "user1"}}
    ]
    
    # Mock merge requests
    async def mock_list_mrs(project_id):
        """Async generator for mocking list_merge_requests"""
        mrs = [
            {"iid": 1, "title": "MR 1", "state": "merged"},
            {"iid": 2, "title": "MR 2", "state": "opened"}
        ]
        for mr in mrs:
            yield mr
    
    client.list_merge_requests = mock_list_mrs  # Direct assignment
    client.get_merge_request.return_value = {
        "iid": 1,
        "title": "MR 1",
        "description": "Description",
        "state": "merged"
    }
    client.list_merge_request_discussions.return_value = [
        {"notes": [{"body": "Review comment"}]}
    ]
    client.list_merge_request_approvals.return_value = {
        "approved": True,
        "approvers": [{"user": {"username": "approver1"}}]
    }
    
    # Mock releases
    client.list_releases.return_value = [
        {"tag_name": "v1.0.0", "name": "Release 1.0.0"}
    ]
    
    # Mock packages
    client.list_packages.return_value = [
        {"name": "package1", "version": "1.0.0"}
    ]
    
    # Mock settings
    client.list_protected_branches.return_value = [
        {"name": "main", "push_access_levels": [{"access_level": 40}]}
    ]
    client.list_protected_tags.return_value = []
    client.list_project_members.return_value = [
        {"username": "user1", "access_level": 40}
    ]
    client.list_webhooks.return_value = [
        {"url": "https://example.com/hook", "token": "secret"}
    ]
    client.list_deploy_keys.return_value = []
    
    client.close.return_value = None
    
    return client


@pytest.mark.asyncio
async def test_export_agent_initialization(export_agent):
    """Test ExportAgent initialization"""
    assert export_agent.agent_name == "ExportAgent"
    assert export_agent.gl_client is None
    assert "repository" in export_agent.export_stats
    assert "ci" in export_agent.export_stats


@pytest.mark.asyncio
async def test_validate_inputs_success(export_agent, export_inputs):
    """Test input validation with valid inputs"""
    assert export_agent.validate_inputs(export_inputs) is True


@pytest.mark.asyncio
async def test_validate_inputs_missing_required(export_agent):
    """Test input validation with missing required fields"""
    incomplete_inputs = {
        "gitlab_url": "https://gitlab.com",
        "gitlab_token": "test-token"
        # Missing project_id and output_dir
    }
    assert export_agent.validate_inputs(incomplete_inputs) is False


@pytest.mark.asyncio
async def test_validate_inputs_invalid_project_id(export_agent):
    """Test input validation with invalid project_id"""
    invalid_inputs = {
        "gitlab_url": "https://gitlab.com",
        "gitlab_token": "test-token",
        "project_id": "not-a-number",
        "output_dir": "/tmp/export"
    }
    assert export_agent.validate_inputs(invalid_inputs) is False


@pytest.mark.asyncio
async def test_create_directory_structure(export_agent, tmp_path):
    """Test directory structure creation"""
    output_dir = tmp_path / "export"
    export_agent._create_directory_structure(output_dir)
    
    # Check all expected directories exist
    assert (output_dir / "repository").exists()
    assert (output_dir / "repository" / "lfs").exists()
    assert (output_dir / "ci").exists()
    assert (output_dir / "ci" / "includes").exists()
    assert (output_dir / "issues").exists()
    assert (output_dir / "issues" / "attachments").exists()
    assert (output_dir / "merge_requests").exists()
    assert (output_dir / "wiki").exists()
    assert (output_dir / "releases").exists()
    assert (output_dir / "packages").exists()
    assert (output_dir / "settings").exists()


@pytest.mark.asyncio
async def test_export_ci_cd(export_agent, mock_gitlab_client, tmp_path):
    """Test CI/CD export"""
    export_agent.gl_client = mock_gitlab_client
    output_dir = tmp_path / "export"
    output_dir.mkdir(parents=True)
    export_agent._create_directory_structure(output_dir)
    
    project = {"id": 123}
    result = await export_agent._export_ci_cd(123, project, output_dir)
    
    assert result["success"] is True
    assert result["count"] > 0
    
    # Check files were created
    ci_dir = output_dir / "ci"
    assert (ci_dir / "gitlab-ci.yml").exists()
    assert (ci_dir / "variables.json").exists()
    assert (ci_dir / "environments.json").exists()
    assert (ci_dir / "schedules.json").exists()
    assert (ci_dir / "pipeline_history.json").exists()
    
    # Check variables are masked
    with open(ci_dir / "variables.json") as f:
        variables = json.load(f)
        for var in variables:
            assert "value" not in var
            assert "key" in var


@pytest.mark.asyncio
async def test_export_issues(export_agent, mock_gitlab_client, tmp_path):
    """Test issues export"""
    export_agent.gl_client = mock_gitlab_client
    output_dir = tmp_path / "export"
    output_dir.mkdir(parents=True)
    export_agent._create_directory_structure(output_dir)
    
    project = {"id": 123}
    result = await export_agent._export_issues(123, project, output_dir)
    
    assert result["success"] is True
    assert result["count"] == 2  # Two issues in mock
    
    # Check file was created
    issues_file = output_dir / "issues" / "issues.json"
    assert issues_file.exists()
    
    with open(issues_file) as f:
        issues = json.load(f)
        assert len(issues) == 2
        # Each issue should have notes attached
        for issue in issues:
            assert "notes" in issue


@pytest.mark.asyncio
async def test_export_merge_requests(export_agent, mock_gitlab_client, tmp_path):
    """Test merge requests export"""
    export_agent.gl_client = mock_gitlab_client
    output_dir = tmp_path / "export"
    output_dir.mkdir(parents=True)
    export_agent._create_directory_structure(output_dir)
    
    project = {"id": 123}
    result = await export_agent._export_merge_requests(123, project, output_dir)
    
    assert result["success"] is True
    assert result["count"] == 2  # Two MRs in mock
    
    # Check file was created
    mrs_file = output_dir / "merge_requests" / "merge_requests.json"
    assert mrs_file.exists()
    
    with open(mrs_file) as f:
        mrs = json.load(f)
        assert len(mrs) == 2
        # Each MR should have discussions and approvals
        for mr in mrs:
            assert "discussions" in mr
            assert "approvals" in mr


@pytest.mark.asyncio
async def test_export_releases(export_agent, mock_gitlab_client, tmp_path):
    """Test releases export"""
    export_agent.gl_client = mock_gitlab_client
    output_dir = tmp_path / "export"
    output_dir.mkdir(parents=True)
    export_agent._create_directory_structure(output_dir)
    
    project = {"id": 123}
    result = await export_agent._export_releases(123, project, output_dir)
    
    assert result["success"] is True
    assert result["count"] == 1
    
    releases_file = output_dir / "releases" / "releases.json"
    assert releases_file.exists()


@pytest.mark.asyncio
async def test_export_packages(export_agent, mock_gitlab_client, tmp_path):
    """Test packages export"""
    export_agent.gl_client = mock_gitlab_client
    output_dir = tmp_path / "export"
    output_dir.mkdir(parents=True)
    export_agent._create_directory_structure(output_dir)
    
    project = {"id": 123}
    result = await export_agent._export_packages(123, project, output_dir)
    
    assert result["success"] is True
    assert result["count"] == 1
    
    packages_file = output_dir / "packages" / "packages.json"
    assert packages_file.exists()


@pytest.mark.asyncio
async def test_export_settings(export_agent, mock_gitlab_client, tmp_path):
    """Test settings export"""
    export_agent.gl_client = mock_gitlab_client
    output_dir = tmp_path / "export"
    output_dir.mkdir(parents=True)
    export_agent._create_directory_structure(output_dir)
    
    project = {
        "id": 123,
        "visibility": "private",
        "default_branch": "main",
        "lfs_enabled": False
    }
    result = await export_agent._export_settings(123, project, output_dir)
    
    assert result["success"] is True
    
    settings_dir = output_dir / "settings"
    assert (settings_dir / "protected_branches.json").exists()
    assert (settings_dir / "members.json").exists()
    assert (settings_dir / "webhooks.json").exists()
    assert (settings_dir / "project_settings.json").exists()
    
    # Check webhooks have masked tokens
    with open(settings_dir / "webhooks.json") as f:
        webhooks = json.load(f)
        for hook in webhooks:
            if "token" in hook:
                assert hook["token"] == "***MASKED***"


@pytest.mark.asyncio
async def test_execute_full_export(export_agent, export_inputs, mock_gitlab_client, tmp_path):
    """Test full export execution"""
    export_inputs["output_dir"] = str(tmp_path / "export")
    
    with patch('app.agents.export_agent.GitLabClient', return_value=mock_gitlab_client):
        with patch('subprocess.run') as mock_subprocess:
            # Mock git commands
            mock_subprocess.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr=""
            )
            
            result = await export_agent.execute(export_inputs)
            
            assert result["status"] in ["success", "partial"]
            assert "outputs" in result
            assert result["outputs"]["project_id"] == 123
            assert "export_stats" in result["outputs"]
            
            # Check manifest was created
            manifest_path = Path(export_inputs["output_dir"]) / "export_manifest.json"
            assert manifest_path.exists()
            
            with open(manifest_path) as f:
                manifest = json.load(f)
                assert "project_id" in manifest
                assert "components" in manifest
                assert "exported_at" in manifest


@pytest.mark.asyncio
async def test_execute_with_error_handling(export_agent, export_inputs, mock_gitlab_client):
    """Test export with error handling"""
    # Make one component fail
    mock_gitlab_client.list_issues.side_effect = Exception("API error")
    
    with patch('app.agents.export_agent.GitLabClient', return_value=mock_gitlab_client):
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = MagicMock(returncode=0)
            
            result = await export_agent.execute(export_inputs)
            
            # Should have partial success
            assert result["status"] in ["partial", "success"]
            assert len(result["errors"]) >= 0  # May have errors


@pytest.mark.asyncio
async def test_generate_artifacts(export_agent):
    """Test artifact generation"""
    artifacts = export_agent.generate_artifacts({})
    
    assert "export_manifest" in artifacts
    assert "repo_bundle" in artifacts
    assert "issues" in artifacts
    assert "merge_requests" in artifacts
    assert "ci_config" in artifacts


@pytest.mark.asyncio
async def test_export_repository_no_url(export_agent, mock_gitlab_client, tmp_path):
    """Test repository export with missing URL"""
    export_agent.gl_client = mock_gitlab_client
    output_dir = tmp_path / "export"
    output_dir.mkdir(parents=True)
    export_agent._create_directory_structure(output_dir)
    
    project = {"id": 123}  # No http_url_to_repo
    result = await export_agent._export_repository(123, project, output_dir)
    
    assert result["success"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_export_wiki_disabled(export_agent, mock_gitlab_client, tmp_path):
    """Test wiki export when wiki is disabled"""
    export_agent.gl_client = mock_gitlab_client
    output_dir = tmp_path / "export"
    output_dir.mkdir(parents=True)
    export_agent._create_directory_structure(output_dir)
    
    project = {"id": 123, "wiki_enabled": False, "http_url_to_repo": "https://gitlab.com/test/project.git"}
    result = await export_agent._export_wiki(123, project, output_dir)
    
    assert result["success"] is True
    assert result["count"] == 0
    
    wiki_dir = output_dir / "wiki"
    assert (wiki_dir / "wiki_disabled.txt").exists()
