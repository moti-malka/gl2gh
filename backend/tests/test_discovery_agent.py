"""Unit tests for Discovery Agent component detection"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.agents.discovery_agent import DiscoveryAgent
from app.clients.gitlab_client import GitLabClient


@pytest.fixture
def mock_gitlab_client():
    """Mock GitLab client for testing"""
    client = Mock(spec=GitLabClient)
    
    # Mock project data
    client.get_project.return_value = {
        "id": 123,
        "name": "test-project",
        "path_with_namespace": "group/test-project",
        "description": "Test project",
        "visibility": "private",
        "archived": False,
        "created_at": "2024-01-01T00:00:00Z",
        "last_activity_at": "2024-01-15T00:00:00Z",
        "web_url": "https://gitlab.com/group/test-project",
        "default_branch": "main"
    }
    
    return client


@pytest.fixture
def discovery_agent():
    """Create discovery agent instance"""
    return DiscoveryAgent()


@pytest.mark.asyncio
class TestDiscoveryAgent:
    """Test cases for DiscoveryAgent"""
    
    async def test_validate_inputs_success(self, discovery_agent):
        """Test input validation with valid inputs"""
        inputs = {
            "gitlab_url": "https://gitlab.com",
            "gitlab_token": "glpat-test-token-123",
            "output_dir": "/tmp/test"
        }
        
        assert discovery_agent.validate_inputs(inputs) is True
    
    async def test_validate_inputs_missing_required(self, discovery_agent):
        """Test input validation with missing required fields"""
        inputs = {
            "gitlab_url": "https://gitlab.com"
            # Missing gitlab_token and output_dir
        }
        
        assert discovery_agent.validate_inputs(inputs) is False
    
    async def test_validate_inputs_invalid_url(self, discovery_agent):
        """Test input validation with invalid URL"""
        inputs = {
            "gitlab_url": "invalid-url",
            "gitlab_token": "glpat-test-token-123",
            "output_dir": "/tmp/test"
        }
        
        assert discovery_agent.validate_inputs(inputs) is False
    
    async def test_validate_inputs_invalid_token(self, discovery_agent):
        """Test input validation with invalid token"""
        inputs = {
            "gitlab_url": "https://gitlab.com",
            "gitlab_token": "short",  # Too short
            "output_dir": "/tmp/test"
        }
        
        assert discovery_agent.validate_inputs(inputs) is False
    
    async def test_detect_repository_component(self, discovery_agent, mock_gitlab_client):
        """Test repository component detection"""
        # Setup mocks
        mock_gitlab_client.list_branches.return_value = [
            {"name": "main"},
            {"name": "develop"}
        ]
        mock_gitlab_client.list_tags.return_value = [
            {"name": "v1.0.0"}
        ]
        mock_gitlab_client.get_commits.return_value = [
            {"id": "abc123"}
        ]
        
        # Get mock project
        project = mock_gitlab_client.get_project(123)
        
        # Detect components
        result = await discovery_agent._detect_project_components(mock_gitlab_client, project)
        
        # Verify repository component
        assert "repository" in result["components"]
        repo_comp = result["components"]["repository"]
        assert repo_comp["enabled"] is True
        assert repo_comp["branches_count"] == 2
        assert repo_comp["tags_count"] == 1
        assert repo_comp["has_content"] is True
    
    async def test_detect_ci_cd_component(self, discovery_agent, mock_gitlab_client):
        """Test CI/CD component detection"""
        # Setup mocks
        mock_gitlab_client.has_ci_config.return_value = True
        mock_gitlab_client.list_pipelines.return_value = [
            {"id": 1, "status": "success"}
        ]
        mock_gitlab_client.list_branches.return_value = []
        mock_gitlab_client.list_tags.return_value = []
        
        project = mock_gitlab_client.get_project(123)
        result = await discovery_agent._detect_project_components(mock_gitlab_client, project)
        
        # Verify CI/CD component
        assert "ci_cd" in result["components"]
        ci_cd_comp = result["components"]["ci_cd"]
        assert ci_cd_comp["enabled"] is True
        assert ci_cd_comp["has_gitlab_ci"] is True
        assert ci_cd_comp["recent_pipelines"] == 1
    
    async def test_detect_issues_component(self, discovery_agent, mock_gitlab_client):
        """Test issues component detection"""
        # Setup mocks
        mock_gitlab_client.list_issues.return_value = [
            {"id": 1, "title": "Issue 1"},
            {"id": 2, "title": "Issue 2"}
        ]
        mock_gitlab_client.list_branches.return_value = []
        mock_gitlab_client.list_tags.return_value = []
        
        project = mock_gitlab_client.get_project(123)
        result = await discovery_agent._detect_project_components(mock_gitlab_client, project)
        
        # Verify issues component
        assert "issues" in result["components"]
        issues_comp = result["components"]["issues"]
        assert issues_comp["enabled"] is True
        assert issues_comp["opened_count"] == 2
        assert issues_comp["has_issues"] is True
    
    async def test_detect_merge_requests_component(self, discovery_agent, mock_gitlab_client):
        """Test merge requests component detection"""
        # Setup mocks
        mock_gitlab_client.list_merge_requests.return_value = [
            {"id": 1, "title": "MR 1"}
        ]
        mock_gitlab_client.list_branches.return_value = []
        mock_gitlab_client.list_tags.return_value = []
        
        project = mock_gitlab_client.get_project(123)
        result = await discovery_agent._detect_project_components(mock_gitlab_client, project)
        
        # Verify merge requests component
        assert "merge_requests" in result["components"]
        mr_comp = result["components"]["merge_requests"]
        assert mr_comp["enabled"] is True
        assert mr_comp["opened_count"] == 1
        assert mr_comp["has_mrs"] is True
    
    async def test_detect_wiki_component(self, discovery_agent, mock_gitlab_client):
        """Test wiki component detection"""
        # Setup mocks
        mock_gitlab_client.has_wiki.return_value = True
        mock_gitlab_client.get_wiki_pages.return_value = [
            {"title": "Home"},
            {"title": "Guide"}
        ]
        mock_gitlab_client.list_branches.return_value = []
        mock_gitlab_client.list_tags.return_value = []
        
        project = mock_gitlab_client.get_project(123)
        result = await discovery_agent._detect_project_components(mock_gitlab_client, project)
        
        # Verify wiki component
        assert "wiki" in result["components"]
        wiki_comp = result["components"]["wiki"]
        assert wiki_comp["enabled"] is True
        assert wiki_comp["pages_count"] == 2
    
    async def test_detect_lfs_component(self, discovery_agent, mock_gitlab_client):
        """Test LFS component detection"""
        # Setup mocks
        mock_gitlab_client.has_lfs.return_value = True
        mock_gitlab_client.list_branches.return_value = []
        mock_gitlab_client.list_tags.return_value = []
        
        project = mock_gitlab_client.get_project(123)
        result = await discovery_agent._detect_project_components(mock_gitlab_client, project)
        
        # Verify LFS component
        assert "lfs" in result["components"]
        lfs_comp = result["components"]["lfs"]
        assert lfs_comp["enabled"] is True
        assert lfs_comp["detected"] is True
    
    async def test_detect_all_components(self, discovery_agent, mock_gitlab_client):
        """Test detection of all 14 component types"""
        # Setup mocks for all components
        mock_gitlab_client.list_branches.return_value = [{"name": "main"}]
        mock_gitlab_client.list_tags.return_value = []
        mock_gitlab_client.get_commits.return_value = []
        mock_gitlab_client.has_ci_config.return_value = True
        mock_gitlab_client.list_pipelines.return_value = []
        mock_gitlab_client.list_issues.return_value = []
        mock_gitlab_client.list_merge_requests.return_value = []
        mock_gitlab_client.has_wiki.return_value = False
        mock_gitlab_client.get_wiki_pages.return_value = []
        mock_gitlab_client.list_releases.return_value = []
        mock_gitlab_client.has_packages.return_value = False
        mock_gitlab_client.list_packages.return_value = []
        mock_gitlab_client.list_hooks.return_value = []
        mock_gitlab_client.list_pipeline_schedules.return_value = []
        mock_gitlab_client.has_lfs.return_value = False
        mock_gitlab_client.list_environments.return_value = []
        mock_gitlab_client.list_protected_branches.return_value = []
        mock_gitlab_client.list_protected_tags.return_value = []
        mock_gitlab_client.list_deploy_keys.return_value = []
        mock_gitlab_client.list_variables.return_value = []
        
        project = mock_gitlab_client.get_project(123)
        result = await discovery_agent._detect_project_components(mock_gitlab_client, project)
        
        # Verify all 14 components are detected
        expected_components = [
            "repository", "ci_cd", "issues", "merge_requests", "wiki",
            "releases", "packages", "webhooks", "schedules", "lfs",
            "environments", "protected_resources", "deploy_keys", "variables"
        ]
        
        for component in expected_components:
            assert component in result["components"], f"Component {component} not detected"
    
    async def test_assess_readiness_low_complexity(self, discovery_agent):
        """Test readiness assessment for low complexity project"""
        project = {
            "id": 123,
            "path_with_namespace": "group/simple-project",
            "archived": False,
            "components": {
                "repository": {"enabled": True, "has_content": True},
                "ci_cd": {"enabled": False},
                "issues": {"enabled": True, "opened_count": 5},
                "merge_requests": {"enabled": True, "opened_count": 2},
                "lfs": {"enabled": False},
                "packages": {"enabled": False}
            }
        }
        
        assessment = discovery_agent.assess_readiness(project)
        
        assert assessment["complexity"] == "low"
        assert len(assessment["blockers"]) == 0
        assert "recommendation" in assessment
    
    async def test_assess_readiness_medium_complexity(self, discovery_agent):
        """Test readiness assessment for medium complexity project"""
        project = {
            "id": 123,
            "path_with_namespace": "group/medium-project",
            "archived": False,
            "components": {
                "repository": {"enabled": True, "has_content": True},
                "ci_cd": {"enabled": True, "has_gitlab_ci": True},
                "issues": {"enabled": True, "opened_count": 10},
                "merge_requests": {"enabled": True, "opened_count": 5},
                "lfs": {"enabled": True, "detected": True},
                "packages": {"enabled": False}
            }
        }
        
        assessment = discovery_agent.assess_readiness(project)
        
        assert assessment["complexity"] == "medium"
        assert len(assessment["blockers"]) > 0
        assert "CI/CD" in assessment["blockers"][0]
    
    async def test_assess_readiness_high_complexity(self, discovery_agent):
        """Test readiness assessment for high complexity project"""
        project = {
            "id": 123,
            "path_with_namespace": "group/complex-project",
            "archived": False,
            "components": {
                "repository": {"enabled": True, "has_content": True},
                "ci_cd": {"enabled": True, "has_gitlab_ci": True},
                "issues": {"enabled": True, "opened_count": 100},
                "merge_requests": {"enabled": True, "opened_count": 50},
                "lfs": {"enabled": True, "detected": True},
                "packages": {"enabled": True, "has_packages": True, "count": 10}
            }
        }
        
        assessment = discovery_agent.assess_readiness(project)
        
        assert assessment["complexity"] == "high"
        assert len(assessment["notes"]) > 0
    
    async def test_generate_coverage(self, discovery_agent):
        """Test coverage.json generation"""
        projects_data = [
            {
                "path_with_namespace": "group/project1",
                "components": {
                    "repository": {"enabled": True, "has_content": True},
                    "ci_cd": {"enabled": True, "has_gitlab_ci": True},
                    "issues": {"enabled": True, "has_issues": True}
                }
            },
            {
                "path_with_namespace": "group/project2",
                "components": {
                    "repository": {"enabled": True, "has_content": False},
                    "ci_cd": {"enabled": False},
                    "issues": {"enabled": True, "has_issues": False}
                }
            }
        ]
        
        coverage = discovery_agent._generate_coverage(projects_data)
        
        assert coverage["summary"]["total_projects"] == 2
        assert "components" in coverage["summary"]
        assert coverage["summary"]["components"]["repository"]["enabled_count"] == 2
        assert coverage["summary"]["components"]["repository"]["projects_with_data"] == 1
        assert coverage["summary"]["components"]["ci_cd"]["projects_with_data"] == 1
    
    async def test_generate_readiness(self, discovery_agent):
        """Test readiness.json generation"""
        projects_data = [
            {
                "path_with_namespace": "group/project1",
                "components": {
                    "repository": {"enabled": True, "has_content": True},
                    "ci_cd": {"enabled": False}
                }
            }
        ]
        
        readiness = discovery_agent._generate_readiness(projects_data)
        
        assert readiness["summary"]["total_projects"] == 1
        assert "ready" in readiness["summary"]
        assert "needs_review" in readiness["summary"]
        assert "complex" in readiness["summary"]
        assert "group/project1" in readiness["projects"]
