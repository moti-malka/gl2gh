"""Unit tests for Transform Agent"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from app.agents.transform_agent import TransformAgent
from app.utils.transformers import TransformationResult


@pytest.fixture
def transform_agent():
    """Create TransformAgent instance"""
    return TransformAgent()


@pytest.fixture
def sample_export_data():
    """Sample export data for testing"""
    return {
        "gitlab_ci_yaml": {
            "stages": ["build", "test"],
            "build_job": {
                "stage": "build",
                "script": ["npm install", "npm run build"]
            }
        },
        "users": [
            {
                "id": 1,
                "username": "johndoe",
                "email": "john@example.com",
                "name": "John Doe"
            }
        ],
        "issues": [
            {
                "iid": 1,
                "title": "Test issue",
                "description": "Test description",
                "state": "opened",
                "labels": ["bug"]
            }
        ],
        "merge_requests": [
            {
                "iid": 1,
                "title": "Test MR",
                "description": "Test MR description",
                "state": "merged",
                "source_branch": "feature",
                "target_branch": "main"
            }
        ],
        "labels": [
            {"name": "bug", "color": "#d73a4a", "description": "Bug reports"}
        ],
        "milestones": [
            {
                "title": "v1.0",
                "description": "First release",
                "due_date": "2024-12-31T00:00:00Z",
                "state": "active"
            }
        ],
        "gitlab_features": ["ci_cd", "issues", "merge_requests"]
    }


@pytest.fixture
def transform_inputs(tmp_path, sample_export_data):
    """Sample transform inputs"""
    return {
        "run_id": "test-run-001",
        "export_data": sample_export_data,
        "output_dir": str(tmp_path / "transform"),
        "gitlab_project": "namespace/project",
        "github_repo": "org/repo",
        "github_org_members": [
            {
                "login": "johndoe",
                "id": 101,
                "email": "john@example.com"
            }
        ]
    }


@pytest.mark.asyncio
class TestTransformAgent:
    """Test cases for TransformAgent"""
    
    async def test_initialization(self, transform_agent):
        """Test TransformAgent initialization"""
        assert transform_agent.agent_name == "TransformAgent"
        assert transform_agent.cicd_transformer is not None
        assert transform_agent.user_mapper is not None
        assert transform_agent.content_transformer is not None
        assert transform_agent.gap_analyzer is not None
    
    async def test_validate_inputs_success(self, transform_agent, transform_inputs):
        """Test input validation with valid inputs"""
        assert transform_agent.validate_inputs(transform_inputs) is True
    
    async def test_validate_inputs_missing_required(self, transform_agent):
        """Test input validation with missing required fields"""
        invalid_inputs = {
            "run_id": "test-run-001"
            # Missing export_data and output_dir
        }
        assert transform_agent.validate_inputs(invalid_inputs) is False
    
    async def test_validate_inputs_missing_export_data(self, transform_agent):
        """Test input validation with missing export_data"""
        invalid_inputs = {
            "run_id": "test-run-001",
            "output_dir": "/tmp/test"
            # Missing export_data
        }
        assert transform_agent.validate_inputs(invalid_inputs) is False
    
    async def test_transform_cicd_success(self, transform_agent, tmp_path):
        """Test successful CI/CD transformation"""
        gitlab_ci = {
            "stages": ["build"],
            "build_job": {
                "stage": "build",
                "script": ["echo 'Building'"]
            }
        }
        
        # Mock the transformer
        mock_result = TransformationResult(
            success=True,
            data={
                "workflow_yaml": "name: CI\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo 'Building'"
            },
            metadata={"conversion_gaps": []},
            warnings=[],
            errors=[]
        )
        
        transform_agent.cicd_transformer.transform = Mock(return_value=mock_result)
        
        result = await transform_agent._transform_cicd(gitlab_ci, tmp_path)
        
        assert result is not None
        assert result["success"] is True
        assert len(result["workflows"]) > 0
        assert (tmp_path / "workflows" / "ci.yml").exists()
    
    async def test_transform_cicd_no_config(self, transform_agent, tmp_path):
        """Test CI/CD transformation with no configuration"""
        result = await transform_agent._transform_cicd(None, tmp_path)
        assert result is None
    
    async def test_transform_cicd_failure(self, transform_agent, tmp_path):
        """Test CI/CD transformation failure"""
        gitlab_ci = {"invalid": "config"}
        
        mock_result = TransformationResult(
            success=False,
            data={},
            metadata={},
            warnings=[],
            errors=[{"message": "Invalid CI config"}]
        )
        
        transform_agent.cicd_transformer.transform = Mock(return_value=mock_result)
        
        result = await transform_agent._transform_cicd(gitlab_ci, tmp_path)
        
        assert result is not None
        assert result["success"] is False
        assert len(result["errors"]) > 0
    
    async def test_map_users_success(self, transform_agent, tmp_path):
        """Test successful user mapping"""
        gitlab_users = [
            {
                "id": 1,
                "username": "johndoe",
                "email": "john@example.com",
                "name": "John Doe"
            }
        ]
        
        github_users = [
            {
                "login": "johndoe",
                "id": 101,
                "email": "john@example.com"
            }
        ]
        
        mock_result = TransformationResult(
            success=True,
            data={
                "mappings": [
                    {
                        "gitlab": {"username": "johndoe"},
                        "github": {"login": "johndoe"},
                        "confidence": "high",
                        "method": "email"
                    }
                ],
                "stats": {"mapped": 1, "unmapped": 0}
            },
            metadata={},
            warnings=[],
            errors=[]
        )
        
        transform_agent.user_mapper.transform = Mock(return_value=mock_result)
        
        result = await transform_agent._map_users(gitlab_users, github_users, tmp_path)
        
        assert result is not None
        assert result["success"] is True
        assert len(result["mappings"]) == 1
        assert result["stats"]["mapped"] == 1
        assert (tmp_path / "user_mappings.json").exists()
    
    async def test_map_users_no_users(self, transform_agent, tmp_path):
        """Test user mapping with no users"""
        result = await transform_agent._map_users([], [], tmp_path)
        assert result is None
    
    async def test_transform_issues_success(self, transform_agent, tmp_path):
        """Test successful issues transformation"""
        issues = [
            {
                "iid": 1,
                "title": "Test issue",
                "description": "Description",
                "state": "opened"
            }
        ]
        
        mock_result = TransformationResult(
            success=True,
            data={
                "title": "Test issue",
                "body": "Description",
                "state": "open"
            },
            metadata={},
            warnings=[],
            errors=[]
        )
        
        transform_agent.content_transformer.transform = Mock(return_value=mock_result)
        
        result = await transform_agent._transform_issues(
            issues,
            "namespace/project",
            "org/repo",
            tmp_path
        )
        
        assert result is not None
        assert result["success"] is True
        assert len(result["issues"]) == 1
        assert (tmp_path / "issues_transformed.json").exists()
    
    async def test_transform_issues_no_issues(self, transform_agent, tmp_path):
        """Test issues transformation with no issues"""
        result = await transform_agent._transform_issues(
            [],
            "namespace/project",
            "org/repo",
            tmp_path
        )
        assert result is None
    
    async def test_transform_merge_requests_success(self, transform_agent, tmp_path):
        """Test successful merge requests transformation"""
        mrs = [
            {
                "iid": 1,
                "title": "Test MR",
                "description": "Description",
                "state": "merged"
            }
        ]
        
        mock_result = TransformationResult(
            success=True,
            data={
                "title": "Test MR",
                "body": "Description",
                "state": "closed"
            },
            metadata={},
            warnings=[],
            errors=[]
        )
        
        transform_agent.content_transformer.transform = Mock(return_value=mock_result)
        
        result = await transform_agent._transform_merge_requests(
            mrs,
            "namespace/project",
            "org/repo",
            tmp_path
        )
        
        assert result is not None
        assert result["success"] is True
        assert len(result["merge_requests"]) == 1
        assert (tmp_path / "pull_requests_transformed.json").exists()
    
    async def test_transform_merge_requests_no_mrs(self, transform_agent, tmp_path):
        """Test merge requests transformation with no MRs"""
        result = await transform_agent._transform_merge_requests(
            [],
            "namespace/project",
            "org/repo",
            tmp_path
        )
        assert result is None
    
    async def test_transform_labels_success(self, transform_agent, tmp_path):
        """Test successful labels transformation"""
        labels = [
            {"name": "bug", "color": "#d73a4a", "description": "Bug reports"},
            {"name": "enhancement", "color": "#a2eeef", "description": "New features"}
        ]
        
        result = await transform_agent._transform_labels(labels, tmp_path)
        
        assert result is not None
        assert result["success"] is True
        assert len(result["labels"]) == 2
        assert (tmp_path / "labels.json").exists()
        
        # Check content
        with open(tmp_path / "labels.json") as f:
            saved_labels = json.load(f)
            assert len(saved_labels) == 2
            assert saved_labels[0]["name"] == "bug"
    
    async def test_transform_labels_no_labels(self, transform_agent, tmp_path):
        """Test labels transformation with no labels"""
        result = await transform_agent._transform_labels([], tmp_path)
        assert result is None
    
    async def test_transform_milestones_success(self, transform_agent, tmp_path):
        """Test successful milestones transformation"""
        milestones = [
            {
                "title": "v1.0",
                "description": "First release",
                "due_date": "2024-12-31T00:00:00Z",
                "state": "active"
            }
        ]
        
        result = await transform_agent._transform_milestones(milestones, tmp_path)
        
        assert result is not None
        assert result["success"] is True
        assert len(result["milestones"]) == 1
        assert (tmp_path / "milestones.json").exists()
        
        # Check content
        with open(tmp_path / "milestones.json") as f:
            saved_milestones = json.load(f)
            assert len(saved_milestones) == 1
            assert saved_milestones[0]["title"] == "v1.0"
            assert saved_milestones[0]["state"] == "open"
    
    async def test_transform_milestones_no_milestones(self, transform_agent, tmp_path):
        """Test milestones transformation with no milestones"""
        result = await transform_agent._transform_milestones([], tmp_path)
        assert result is None
    
    async def test_analyze_gaps_success(self, transform_agent, tmp_path):
        """Test successful gap analysis"""
        workflows_result = {
            "conversion_gaps": [
                {"feature": "include", "severity": "high"}
            ]
        }
        
        user_mappings_result = {
            "stats": {"unmapped": 2}
        }
        
        mock_result = TransformationResult(
            success=True,
            data={
                "gaps": [
                    {"category": "cicd", "feature": "include", "severity": "high"}
                ],
                "summary": {"total_gaps": 1},
                "categorized_gaps": {
                    "cicd": [{"feature": "include", "severity": "high"}]
                }
            },
            metadata={},
            warnings=[],
            errors=[]
        )
        
        transform_agent.gap_analyzer.transform = Mock(return_value=mock_result)
        transform_agent.gap_analyzer.generate_gap_report = Mock(return_value="# Gap Analysis Report\n")
        
        result = await transform_agent._analyze_gaps(
            workflows_result,
            user_mappings_result,
            ["ci_cd", "issues"],
            tmp_path
        )
        
        assert result is not None
        assert result["success"] is True
        assert len(result["gaps"]) > 0
        assert (tmp_path / "conversion_gaps.json").exists()
        assert (tmp_path / "conversion_gaps.md").exists()
    
    async def test_full_execute_success(self, transform_agent, transform_inputs):
        """Test full transformation execution"""
        # Mock all transformers
        cicd_mock = TransformationResult(
            success=True,
            data={"workflow_yaml": "name: CI"},
            metadata={"conversion_gaps": []},
            warnings=[],
            errors=[]
        )
        
        user_mock = TransformationResult(
            success=True,
            data={
                "mappings": [{"gitlab": {"username": "johndoe"}, "github": {"login": "johndoe"}}],
                "stats": {"mapped": 1, "unmapped": 0}
            },
            metadata={},
            warnings=[],
            errors=[]
        )
        
        content_mock = TransformationResult(
            success=True,
            data={"title": "Test"},
            metadata={},
            warnings=[],
            errors=[]
        )
        
        gap_mock = TransformationResult(
            success=True,
            data={
                "gaps": [],
                "summary": {},
                "categorized_gaps": {}
            },
            metadata={},
            warnings=[],
            errors=[]
        )
        
        transform_agent.cicd_transformer.transform = Mock(return_value=cicd_mock)
        transform_agent.user_mapper.transform = Mock(return_value=user_mock)
        transform_agent.content_transformer.transform = Mock(return_value=content_mock)
        transform_agent.content_transformer.set_user_mappings = Mock()
        transform_agent.gap_analyzer.transform = Mock(return_value=gap_mock)
        transform_agent.gap_analyzer.generate_gap_report = Mock(return_value="# Report")
        
        result = await transform_agent.execute(transform_inputs)
        
        assert result["status"] == "success"
        assert "outputs" in result
        assert result["outputs"]["transform_complete"] is True
        assert result["outputs"]["run_id"] == "test-run-001"
        assert len(result["artifacts"]) > 0
    
    async def test_execute_with_minimal_data(self, transform_agent, tmp_path):
        """Test execution with minimal export data"""
        minimal_inputs = {
            "run_id": "test-run-002",
            "export_data": {},
            "output_dir": str(tmp_path / "transform")
        }
        
        # Mock gap analyzer
        gap_mock = TransformationResult(
            success=True,
            data={"gaps": [], "summary": {}, "categorized_gaps": {}},
            metadata={},
            warnings=[],
            errors=[]
        )
        transform_agent.gap_analyzer.transform = Mock(return_value=gap_mock)
        transform_agent.gap_analyzer.generate_gap_report = Mock(return_value="# Report")
        
        result = await transform_agent.execute(minimal_inputs)
        
        assert result["status"] == "success"
        assert result["outputs"]["transform_complete"] is True
    
    async def test_execute_with_transformation_errors(self, transform_agent, transform_inputs):
        """Test execution with transformation errors"""
        # Mock transformers with errors
        cicd_mock = TransformationResult(
            success=False,
            data={},
            metadata={},
            warnings=[],
            errors=[{"message": "CI/CD transformation failed"}]
        )
        
        gap_mock = TransformationResult(
            success=True,
            data={"gaps": [], "summary": {}, "categorized_gaps": {}},
            metadata={},
            warnings=[],
            errors=[]
        )
        
        transform_agent.cicd_transformer.transform = Mock(return_value=cicd_mock)
        transform_agent.gap_analyzer.transform = Mock(return_value=gap_mock)
        transform_agent.gap_analyzer.generate_gap_report = Mock(return_value="# Report")
        
        result = await transform_agent.execute(transform_inputs)
        
        assert result["status"] == "partial"
        assert len(result["errors"]) > 0
    
    async def test_execute_exception_handling(self, transform_agent):
        """Test execution with exception"""
        invalid_inputs = {
            "run_id": "test-run-003",
            "export_data": {"invalid": "data"},
            "output_dir": "/invalid/path/that/cannot/be/created/with/no/perms"
        }
        
        # This should trigger an exception due to permission error
        result = await transform_agent.execute(invalid_inputs)
        
        # Should handle the error gracefully
        assert result["status"] in ["failed", "success"]
        if result["status"] == "failed":
            assert len(result["errors"]) > 0
    
    async def test_generate_artifacts(self, transform_agent):
        """Test artifact generation"""
        artifacts = transform_agent.generate_artifacts({})
        
        assert "workflows" in artifacts
        assert "user_mappings" in artifacts
        assert "issues_transformed" in artifacts
        assert "pull_requests_transformed" in artifacts
        assert "labels" in artifacts
        assert "milestones" in artifacts
        assert "conversion_gaps" in artifacts
        assert "conversion_gaps_report" in artifacts
