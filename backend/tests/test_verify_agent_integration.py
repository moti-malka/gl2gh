"""Integration test for Verify Agent - end-to-end with mock GitHub API"""

import pytest
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from app.agents.verify_agent import VerifyAgent


@pytest.fixture
def integration_test_dir(tmp_path):
    """Create integration test directory"""
    test_dir = tmp_path / "integration_test"
    test_dir.mkdir()
    return test_dir


@pytest.fixture
def comprehensive_expected_state():
    """Comprehensive expected state for migration verification"""
    return {
        "repository": {
            "branch_count": 5,
            "tag_count": 10,
            "lfs_enabled": True
        },
        "ci_cd": {
            "workflow_count": 3,
            "environment_count": 2
        },
        "issues": {
            "issue_count": 50
        },
        "pull_requests": {
            "pr_count": 20
        },
        "wiki": {
            "wiki_enabled": True
        },
        "releases": {
            "release_count": 5
        },
        "packages": {
            "package_count": 0
        },
        "settings": {
            "protected_branches": 2,
            "collaborators": 5
        },
        "preservation": {
            "preservation_expected": True
        }
    }


class MockGitHubAPI:
    """Mock GitHub API for integration testing"""
    
    def __init__(self, scenario="perfect_match"):
        self.scenario = scenario
        self.call_count = 0
    
    async def get(self, url, params=None, **kwargs):
        """Mock GET requests to GitHub API"""
        self.call_count += 1
        response = MagicMock()
        
        # Repository endpoint
        if url == "/repos/test-owner/test-repo" and "branches" not in url:
            response.status_code = 200
            response.json.return_value = {
                "full_name": "test-owner/test-repo",
                "default_branch": "main",
                "has_wiki": True,
                "has_issues": True,
                "has_projects": True,
                "has_discussions": True,
                "private": False
            }
        
        # Branches endpoint
        elif "branches" in url and "protection" not in url:
            response.status_code = 200
            branches = [
                {"name": "main", "protected": True},
                {"name": "develop", "protected": True},
                {"name": "feature-1", "protected": False},
                {"name": "feature-2", "protected": False},
                {"name": "hotfix", "protected": False}
            ]
            if self.scenario == "missing_branches":
                branches = branches[:3]  # Only 3 branches instead of 5
            response.json.return_value = branches
        
        # Tags endpoint
        elif "tags" in url:
            response.status_code = 200
            tags = [{"name": f"v{i}.0.0"} for i in range(1, 11)]
            if self.scenario == "missing_tags":
                tags = tags[:7]  # Only 7 tags instead of 10
            response.json.return_value = tags
        
        # Commits endpoint
        elif "commits" in url:
            response.status_code = 200
            response.headers = {"Link": '<...?page=100>; rel="last"'}
            response.json.return_value = []
        
        # .gitattributes for LFS
        elif ".gitattributes" in url:
            response.status_code = 200 if self.scenario != "missing_lfs" else 404
            response.json.return_value = {"content": "KiBmaWx0ZXI9bGZz"}  # "* filter=lfs" base64
        
        # Workflows endpoint
        elif "workflows" in url and "contents" not in url:
            response.status_code = 200
            workflows = [
                {"name": "CI", "path": ".github/workflows/ci.yml"},
                {"name": "Deploy", "path": ".github/workflows/deploy.yml"},
                {"name": "Test", "path": ".github/workflows/test.yml"}
            ]
            if self.scenario == "missing_workflows":
                workflows = workflows[:1]  # Only 1 workflow instead of 3
            response.json.return_value = {"workflows": workflows}
        
        # Workflow file contents
        elif "contents" in url and ".github/workflows" in url:
            response.status_code = 200
            import base64
            yaml_content = "name: CI\non:\n  push:\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v2"
            response.json.return_value = {
                "content": base64.b64encode(yaml_content.encode()).decode()
            }
        
        # Environments endpoint
        elif "environments" in url:
            response.status_code = 200
            envs = [
                {"name": "production"},
                {"name": "staging"}
            ]
            if self.scenario == "missing_environments":
                envs = envs[:1]
            response.json.return_value = {"environments": envs}
        
        # Secrets endpoint
        elif "secrets" in url:
            response.status_code = 200
            response.json.return_value = {"total_count": 10}
        
        # Variables endpoint
        elif "variables" in url:
            response.status_code = 200
            response.json.return_value = {"total_count": 5}
        
        # Issues endpoint
        elif "issues" in url:
            response.status_code = 200
            if self.scenario == "missing_issues":
                response.headers = {"Link": '<...?page=30>; rel="last"'}  # Only 30 issues
            else:
                response.headers = {"Link": '<...?page=50>; rel="last"'}
        
        # Labels endpoint
        elif "labels" in url:
            response.status_code = 200
            response.json.return_value = [
                {"name": "bug"},
                {"name": "enhancement"},
                {"name": "documentation"}
            ]
        
        # Milestones endpoint
        elif "milestones" in url:
            response.status_code = 200
            response.json.return_value = [
                {"title": "v1.0"},
                {"title": "v2.0"}
            ]
        
        # Pull requests endpoint
        elif "pulls" in url:
            response.status_code = 200
            response.headers = {"Link": '<...?page=20>; rel="last"'}
        
        # Releases endpoint
        elif "releases" in url:
            response.status_code = 200
            releases = [
                {
                    "tag_name": f"v{i}.0.0",
                    "name": f"Release {i}.0.0",
                    "assets": [
                        {"name": f"binary-{i}.tar.gz", "size": 1024000}
                    ]
                }
                for i in range(1, 6)
            ]
            if self.scenario == "missing_releases":
                releases = releases[:3]
            response.json.return_value = releases
        
        # Collaborators endpoint
        elif "collaborators" in url:
            response.status_code = 200
            response.json.return_value = [
                {"login": f"user{i}"} for i in range(1, 6)
            ]
        
        # Webhooks endpoint
        elif "hooks" in url:
            response.status_code = 200
            response.json.return_value = [
                {"id": 1, "url": "https://example.com/webhook"}
            ]
        
        # Migration directory
        elif ".github/migration" in url:
            if self.scenario == "missing_preservation":
                response.status_code = 404
            else:
                response.status_code = 200
                response.json.return_value = [
                    {"name": "id_mappings.json", "type": "file"},
                    {"name": "migration_metadata.json", "type": "file"},
                    {"name": "export_manifest.json", "type": "file"}
                ]
        
        else:
            response.status_code = 404
            response.json.return_value = {"message": "Not Found"}
        
        return response
    
    async def aclose(self):
        """Mock close method"""
        pass


@pytest.mark.asyncio
async def test_verify_agent_perfect_match(integration_test_dir, comprehensive_expected_state):
    """Test verification with perfect match between expected and actual"""
    agent = VerifyAgent()
    
    inputs = {
        "github_token": "test_token",
        "github_repo": "test-owner/test-repo",
        "expected_state": comprehensive_expected_state,
        "output_dir": str(integration_test_dir)
    }
    
    # Mock the httpx client
    mock_api = MockGitHubAPI(scenario="perfect_match")
    
    with patch('httpx.AsyncClient', return_value=mock_api):
        result = await agent.execute(inputs)
    
    # Verify overall result
    assert result["status"] == "success"
    assert result["outputs"]["verify_complete"] is True
    assert result["outputs"]["total_errors"] == 0
    
    # Verify artifacts created
    verify_dir = Path(integration_test_dir) / "verify"
    assert verify_dir.exists()
    
    # Check verify_report.json
    report_file = verify_dir / "verify_report.json"
    assert report_file.exists()
    with open(report_file) as f:
        report = json.load(f)
    
    assert report["overall_status"] == "SUCCESS"
    assert report["summary"]["components_passed"] == 9
    assert report["summary"]["components_failed"] == 0
    
    # Check verify_summary.md
    summary_file = verify_dir / "verify_summary.md"
    assert summary_file.exists()
    with open(summary_file) as f:
        summary = f.read()
    
    assert "Migration Verification Summary" in summary
    assert "SUCCESS" in summary
    
    # Check component_status.json
    status_file = verify_dir / "component_status.json"
    assert status_file.exists()
    with open(status_file) as f:
        status = json.load(f)
    
    assert all(comp["status"] == "success" for comp in status.values())


@pytest.mark.asyncio
async def test_verify_agent_with_discrepancies(integration_test_dir, comprehensive_expected_state):
    """Test verification with discrepancies"""
    agent = VerifyAgent()
    
    inputs = {
        "github_token": "test_token",
        "github_repo": "test-owner/test-repo",
        "expected_state": comprehensive_expected_state,
        "output_dir": str(integration_test_dir)
    }
    
    # Mock with missing branches scenario
    mock_api = MockGitHubAPI(scenario="missing_branches")
    
    with patch('httpx.AsyncClient', return_value=mock_api):
        result = await agent.execute(inputs)
    
    # Should have warnings but not fail
    assert result["status"] in ["success", "partial"]
    assert result["outputs"]["verify_complete"] is True
    
    # Check for warnings in report
    verify_dir = Path(integration_test_dir) / "verify"
    report_file = verify_dir / "verify_report.json"
    with open(report_file) as f:
        report = json.load(f)
    
    # Should have some warnings about branch count mismatch
    assert report["summary"]["total_warnings"] > 0 or report["summary"]["total_discrepancies"] > 0


@pytest.mark.asyncio
async def test_verify_agent_multiple_errors(integration_test_dir, comprehensive_expected_state):
    """Test verification with multiple missing components"""
    agent = VerifyAgent()
    
    # Create a scenario with many missing items
    comprehensive_expected_state["repository"]["branch_count"] = 10  # Expect more than available
    comprehensive_expected_state["ci_cd"]["workflow_count"] = 10  # Expect more workflows
    comprehensive_expected_state["releases"]["release_count"] = 10  # Expect more releases
    
    inputs = {
        "github_token": "test_token",
        "github_repo": "test-owner/test-repo",
        "expected_state": comprehensive_expected_state,
        "output_dir": str(integration_test_dir)
    }
    
    mock_api = MockGitHubAPI(scenario="missing_workflows")
    
    with patch('httpx.AsyncClient', return_value=mock_api):
        result = await agent.execute(inputs)
    
    # Should have warnings
    assert result["outputs"]["total_warnings"] > 0
    
    # Check discrepancies report
    verify_dir = Path(integration_test_dir) / "verify"
    discrepancies_file = verify_dir / "discrepancies.json"
    with open(discrepancies_file) as f:
        discrepancies = json.load(f)
    
    assert discrepancies["total"] > 0
    assert "by_severity" in discrepancies


@pytest.mark.asyncio
async def test_verify_agent_repository_not_found(integration_test_dir, comprehensive_expected_state):
    """Test verification when repository doesn't exist"""
    agent = VerifyAgent()
    
    inputs = {
        "github_token": "test_token",
        "github_repo": "test-owner/nonexistent-repo",
        "expected_state": comprehensive_expected_state,
        "output_dir": str(integration_test_dir)
    }
    
    mock_api = AsyncMock()
    not_found_response = MagicMock()
    not_found_response.status_code = 404
    not_found_response.json.return_value = {"message": "Not Found"}
    mock_api.get = AsyncMock(return_value=not_found_response)
    mock_api.aclose = AsyncMock()
    
    with patch('httpx.AsyncClient', return_value=mock_api):
        result = await agent.execute(inputs)
    
    # Should fail with repository error
    assert result["status"] in ["failed", "partial"]
    
    # Check that error is recorded
    verify_dir = Path(integration_test_dir) / "verify"
    report_file = verify_dir / "verify_report.json"
    with open(report_file) as f:
        report = json.load(f)
    
    # Repository component should have error
    assert report["components"]["repository"]["status"] == "error"


@pytest.mark.asyncio
async def test_verify_agent_invalid_inputs(integration_test_dir):
    """Test verification with invalid inputs"""
    agent = VerifyAgent()
    
    # Missing required fields
    invalid_inputs = {
        "github_token": "test_token",
        "github_repo": "test-owner/test-repo"
        # Missing expected_state and output_dir
    }
    
    assert agent.validate_inputs(invalid_inputs) is False


@pytest.mark.asyncio
async def test_verify_agent_comprehensive_statistics(integration_test_dir, comprehensive_expected_state):
    """Test that all statistics are properly collected"""
    agent = VerifyAgent()
    
    inputs = {
        "github_token": "test_token",
        "github_repo": "test-owner/test-repo",
        "expected_state": comprehensive_expected_state,
        "output_dir": str(integration_test_dir)
    }
    
    mock_api = MockGitHubAPI(scenario="perfect_match")
    
    with patch('httpx.AsyncClient', return_value=mock_api):
        result = await agent.execute(inputs)
    
    # Check component status
    verify_dir = Path(integration_test_dir) / "verify"
    status_file = verify_dir / "component_status.json"
    with open(status_file) as f:
        status = json.load(f)
    
    # Verify statistics are collected for each component
    assert "repository" in status
    assert "stats" in status["repository"]
    assert "branch_count" in status["repository"]["stats"]
    assert "tag_count" in status["repository"]["stats"]
    
    assert "ci_cd" in status
    assert "stats" in status["ci_cd"]
    assert "workflow_count" in status["ci_cd"]["stats"]
    
    assert "issues" in status
    assert "stats" in status["issues"]
    
    # Verify check counts
    for component, data in status.items():
        assert "checks_total" in data
        assert "checks_passed" in data
        assert data["checks_total"] >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
