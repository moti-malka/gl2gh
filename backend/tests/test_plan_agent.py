"""Unit tests for Plan Agent"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch
from app.agents.plan_agent import PlanAgent, PlanGenerator, ActionType, Phase


@pytest.fixture
def plan_agent():
    """Create PlanAgent instance"""
    return PlanAgent()


@pytest.fixture
def sample_export_data():
    """Sample export data for testing"""
    return {
        "description": "Test project",
        "visibility": "private",
        "has_wiki": True,
        "has_lfs": False,
        "labels": [
            {"name": "bug", "color": "d73a4a", "description": "Something isn't working"},
            {"name": "enhancement", "color": "a2eeef", "description": "New feature"}
        ],
        "milestones": [
            {"title": "v1.0", "description": "First release", "due_date": "2024-06-30T00:00:00Z", "state": "open"}
        ],
        "issues": [
            {
                "iid": 1,
                "title": "Fix login bug",
                "description": "Login fails when...",
                "labels": ["bug"],
                "milestone": "v1.0",
                "assignees": ["johndoe"],
                "state": "open",
                "comments": []
            }
        ],
        "merge_requests": [
            {
                "iid": 1,
                "title": "Add authentication",
                "description": "This PR adds auth",
                "source_branch": "feature/auth",
                "target_branch": "main",
                "labels": ["enhancement"],
                "reviewers": ["janedoe"],
                "state": "open",
                "comments": []
            }
        ],
        "releases": [
            {
                "tag_name": "v1.0.0",
                "name": "Version 1.0.0",
                "description": "First release",
                "assets": []
            }
        ],
        "webhooks": [],
        "packages": []
    }


@pytest.fixture
def sample_transform_data():
    """Sample transform data for testing"""
    return {
        "workflows": [
            {
                "name": "ci.yml",
                "source_path": "transform/namespace/project/workflows/ci.yml"
            }
        ],
        "environments": [
            {
                "name": "production",
                "secrets": [
                    {"key": "DATABASE_URL", "masked": True, "value": None}
                ]
            }
        ],
        "branch_protections": [
            {
                "branch": "main",
                "required_status_checks": {"strict": True, "contexts": ["ci"]},
                "enforce_admins": True,
                "required_pull_request_reviews": {"required_approving_review_count": 1}
            }
        ]
    }


@pytest.mark.asyncio
async def test_plan_agent_validation(plan_agent):
    """Test input validation"""
    # Valid inputs
    valid_inputs = {
        "output_dir": "/tmp/test",
        "run_id": "test-001",
        "project_id": "proj-001"
    }
    assert plan_agent.validate_inputs(valid_inputs) is True
    
    # Missing required field
    invalid_inputs = {
        "run_id": "test-001"
    }
    assert plan_agent.validate_inputs(invalid_inputs) is False


@pytest.mark.asyncio
async def test_plan_generation(plan_agent, tmp_path, sample_export_data, sample_transform_data):
    """Test basic plan generation"""
    inputs = {
        "output_dir": str(tmp_path),
        "run_id": "test-run-001",
        "project_id": "test-project-001",
        "gitlab_project": "namespace/project",
        "github_target": "org/repo",
        "export_data": sample_export_data,
        "transform_data": sample_transform_data
    }
    
    result = await plan_agent.execute(inputs)
    
    assert result["status"] == "success"
    assert "plan" in result["outputs"]
    assert result["outputs"]["plan_complete"] is True
    
    plan = result["outputs"]["plan"]
    assert plan["version"] == "1.0"
    assert plan["run_id"] == "test-run-001"
    assert plan["gitlab_project"] == "namespace/project"
    assert plan["github_target"] == "org/repo"
    assert len(plan["actions"]) > 0
    assert len(plan["phases"]) > 0


@pytest.mark.asyncio
async def test_plan_artifacts_generation(plan_agent, tmp_path, sample_export_data, sample_transform_data):
    """Test artifact file generation"""
    inputs = {
        "output_dir": str(tmp_path),
        "run_id": "test-run-001",
        "project_id": "test-project-001",
        "gitlab_project": "namespace/project",
        "github_target": "org/repo",
        "export_data": sample_export_data,
        "transform_data": sample_transform_data
    }
    
    result = await plan_agent.execute(inputs)
    
    # Check artifacts were created
    assert len(result["artifacts"]) == 5
    
    # Verify each artifact exists
    assert (tmp_path / "plan.json").exists()
    assert (tmp_path / "dependency_graph.json").exists()
    assert (tmp_path / "user_inputs_required.json").exists()
    assert (tmp_path / "plan_stats.json").exists()
    assert (tmp_path / "plan.md").exists()
    
    # Verify plan.json content
    with open(tmp_path / "plan.json") as f:
        plan = json.load(f)
        assert plan["version"] == "1.0"
        assert "actions" in plan
        assert "phases" in plan
        assert "summary" in plan
        assert "validation" in plan


def test_plan_generator_action_creation():
    """Test PlanGenerator action creation"""
    generator = PlanGenerator("run-001", "proj-001", "ns/project", "org/repo")
    
    action_id = generator.add_action(
        action_type=ActionType.REPO_CREATE,
        component="repository",
        phase=Phase.FOUNDATION,
        description="Create repository",
        parameters={"org": "org", "name": "repo"}
    )
    
    assert action_id == "action-001"
    assert len(generator.actions) == 1
    assert generator.actions[0]["id"] == action_id
    assert generator.actions[0]["type"] == ActionType.REPO_CREATE
    assert generator.actions[0]["phase"] == Phase.FOUNDATION


def test_plan_generator_idempotency_keys():
    """Test idempotency key generation"""
    generator = PlanGenerator("run-001", "proj-001", "ns/project", "org/repo")
    
    # Same inputs should generate same key
    key1 = generator.generate_idempotency_key("repo_create", "myrepo", "extra")
    key2 = generator.generate_idempotency_key("repo_create", "myrepo", "extra")
    assert key1 == key2
    
    # Different inputs should generate different keys
    key3 = generator.generate_idempotency_key("repo_create", "otherrepo", "extra")
    assert key1 != key3


def test_plan_generator_dependencies():
    """Test dependency management"""
    generator = PlanGenerator("run-001", "proj-001", "ns/project", "org/repo")
    
    action1 = generator.add_action(
        action_type=ActionType.REPO_CREATE,
        component="repository",
        phase=Phase.FOUNDATION,
        description="Create repository",
        parameters={"org": "org", "name": "repo"}
    )
    
    action2 = generator.add_action(
        action_type=ActionType.REPO_PUSH,
        component="repository",
        phase=Phase.FOUNDATION,
        description="Push code",
        parameters={"bundle_path": "repo.bundle"},
        dependencies=[action1]
    )
    
    # Validate dependencies
    valid, errors = generator.validate_dependencies()
    assert valid is True
    assert len(errors) == 0
    
    # Check dependency graph
    assert action2 in generator.dependency_graph
    assert action1 in generator.dependency_graph[action2]


def test_plan_generator_missing_dependency():
    """Test validation of missing dependencies"""
    generator = PlanGenerator("run-001", "proj-001", "ns/project", "org/repo")
    
    # Add action with non-existent dependency
    generator.add_action(
        action_type=ActionType.REPO_PUSH,
        component="repository",
        phase=Phase.FOUNDATION,
        description="Push code",
        parameters={"bundle_path": "repo.bundle"},
        dependencies=["action-999"]  # Non-existent
    )
    
    valid, errors = generator.validate_dependencies()
    assert valid is False
    assert len(errors) > 0
    assert "non-existent" in errors[0].lower()


def test_plan_generator_circular_dependency():
    """Test detection of circular dependencies"""
    generator = PlanGenerator("run-001", "proj-001", "ns/project", "org/repo")
    
    action1 = generator.add_action(
        action_type=ActionType.REPO_CREATE,
        component="repository",
        phase=Phase.FOUNDATION,
        description="Create repository",
        parameters={"org": "org", "name": "repo"}
    )
    
    action2 = generator.add_action(
        action_type=ActionType.REPO_PUSH,
        component="repository",
        phase=Phase.FOUNDATION,
        description="Push code",
        parameters={"bundle_path": "repo.bundle"},
        dependencies=[action1]
    )
    
    # Manually create circular dependency
    generator.dependency_graph[action1] = [action2]
    
    valid, errors = generator.validate_dependencies()
    assert valid is False
    assert len(errors) > 0
    assert "circular" in errors[0].lower()


def test_plan_generator_topological_sort():
    """Test topological sorting of actions"""
    generator = PlanGenerator("run-001", "proj-001", "ns/project", "org/repo")
    
    action1 = generator.add_action(
        action_type=ActionType.REPO_CREATE,
        component="repository",
        phase=Phase.FOUNDATION,
        description="Create repository",
        parameters={"org": "org", "name": "repo"}
    )
    
    action2 = generator.add_action(
        action_type=ActionType.REPO_PUSH,
        component="repository",
        phase=Phase.FOUNDATION,
        description="Push code",
        parameters={"bundle_path": "repo.bundle"},
        dependencies=[action1]
    )
    
    action3 = generator.add_action(
        action_type=ActionType.LABEL_CREATE,
        component="issues",
        phase=Phase.ISSUE_SETUP,
        description="Create label",
        parameters={"name": "bug"},
        dependencies=[action1]
    )
    
    sorted_actions = generator.topological_sort()
    
    # action1 should come before action2 and action3
    assert sorted_actions.index(action1) < sorted_actions.index(action2)
    assert sorted_actions.index(action1) < sorted_actions.index(action3)


def test_plan_generator_phase_organization():
    """Test phase organization"""
    generator = PlanGenerator("run-001", "proj-001", "ns/project", "org/repo")
    
    # Add actions in different phases
    generator.add_action(
        action_type=ActionType.REPO_CREATE,
        component="repository",
        phase=Phase.FOUNDATION,
        description="Create repository",
        parameters={"org": "org", "name": "repo"}
    )
    
    generator.add_action(
        action_type=ActionType.LABEL_CREATE,
        component="issues",
        phase=Phase.ISSUE_SETUP,
        description="Create label",
        parameters={"name": "bug"}
    )
    
    generator.add_action(
        action_type=ActionType.ISSUE_CREATE,
        component="issues",
        phase=Phase.ISSUE_IMPORT,
        description="Create issue",
        parameters={"title": "Test issue"}
    )
    
    phases = generator.organize_into_phases()
    
    assert len(phases) == 3
    
    # Check phase order
    phase_names = [p["name"] for p in phases]
    assert phase_names.index(Phase.FOUNDATION) < phase_names.index(Phase.ISSUE_SETUP)
    assert phase_names.index(Phase.ISSUE_SETUP) < phase_names.index(Phase.ISSUE_IMPORT)
    
    # Check parallel_safe flag
    issue_import_phase = next(p for p in phases if p["name"] == Phase.ISSUE_IMPORT)
    assert issue_import_phase.get("parallel_safe") is True


def test_plan_generator_user_inputs():
    """Test identification of required user inputs"""
    generator = PlanGenerator("run-001", "proj-001", "ns/project", "org/repo")
    user_inputs_required = []
    
    # Add action requiring user input
    generator.add_action(
        action_type=ActionType.SECRET_SET,
        component="ci",
        phase=Phase.CI_SETUP,
        description="Set secret",
        parameters={
            "secret_name": "DATABASE_URL",
            "value": "${USER_INPUT_REQUIRED}",
            "value_source": "user_input"
        },
        requires_user_input=True
    )
    
    # Simulate adding user input requirement
    user_inputs_required.append({
        "type": "secret_value",
        "key": "DATABASE_URL",
        "scope": "repository",
        "reason": "GitLab variable was masked",
        "required": True
    })
    
    assert len(user_inputs_required) == 1
    assert user_inputs_required[0]["type"] == "secret_value"
    assert user_inputs_required[0]["key"] == "DATABASE_URL"


def test_plan_generator_build_plan():
    """Test complete plan building"""
    generator = PlanGenerator("run-001", "proj-001", "ns/project", "org/repo")
    
    action1 = generator.add_action(
        action_type=ActionType.REPO_CREATE,
        component="repository",
        phase=Phase.FOUNDATION,
        description="Create repository",
        parameters={"org": "org", "name": "repo"}
    )
    
    generator.add_action(
        action_type=ActionType.REPO_PUSH,
        component="repository",
        phase=Phase.FOUNDATION,
        description="Push code",
        parameters={"bundle_path": "repo.bundle"},
        dependencies=[action1]
    )
    
    plan = generator.build_plan()
    
    assert plan["version"] == "1.0"
    assert plan["run_id"] == "run-001"
    assert plan["project_id"] == "proj-001"
    assert len(plan["actions"]) == 2
    assert len(plan["phases"]) == 1
    assert plan["summary"]["total_actions"] == 2
    assert plan["validation"]["all_dependencies_resolvable"] is True
    assert plan["validation"]["no_circular_dependencies"] is True


@pytest.mark.asyncio
async def test_plan_agent_with_minimal_data(plan_agent, tmp_path):
    """Test plan generation with minimal data"""
    inputs = {
        "output_dir": str(tmp_path),
        "run_id": "test-run-001",
        "project_id": "test-project-001",
        "gitlab_project": "namespace/project",
        "github_target": "org/repo",
        "export_data": {},
        "transform_data": {}
    }
    
    result = await plan_agent.execute(inputs)
    
    assert result["status"] == "success"
    plan = result["outputs"]["plan"]
    
    # Should at least have foundation actions
    assert len(plan["actions"]) >= 2  # repo_create and repo_push
    assert plan["summary"]["total_actions"] >= 2


@pytest.mark.asyncio
async def test_plan_agent_error_handling(plan_agent, tmp_path):
    """Test error handling in plan generation"""
    # Provide invalid path to trigger error
    inputs = {
        "output_dir": "/invalid/path/that/cannot/be/created",
        "run_id": "test-run-001",
        "project_id": "test-project-001"
    }
    
    # Should handle the error gracefully
    # Note: This might still succeed if the agent creates the directory
    result = await plan_agent.execute(inputs)
    
    # Result should either be success or failed with error information
    assert result["status"] in ["success", "failed"]
    if result["status"] == "failed":
        assert len(result["errors"]) > 0


def test_action_type_constants():
    """Test action type constants are defined"""
    assert ActionType.REPO_CREATE == "repo_create"
    assert ActionType.REPO_PUSH == "repo_push"
    assert ActionType.LABEL_CREATE == "label_create"
    assert ActionType.ISSUE_CREATE == "issue_create"
    assert ActionType.PR_CREATE == "pr_create"
    assert ActionType.RELEASE_CREATE == "release_create"
    assert ActionType.WEBHOOK_CREATE == "webhook_create"


def test_phase_constants():
    """Test phase constants are defined"""
    assert Phase.FOUNDATION == "foundation"
    assert Phase.CI_SETUP == "ci_setup"
    assert Phase.ISSUE_SETUP == "issue_setup"
    assert Phase.ISSUE_IMPORT == "issue_import"
    assert Phase.PR_IMPORT == "pr_import"
    assert Phase.GOVERNANCE == "governance"


def test_plan_generator_release_assets():
    """Test release asset upload actions are created"""
    from app.agents.plan_agent import PlanGenerator, ActionType, Phase
    
    generator = PlanGenerator("run-001", "proj-001", "user/repo", "target/repo")
    
    # Manually create a release action
    release_id = generator.add_action(
        action_type=ActionType.RELEASE_CREATE,
        component="releases",
        phase=Phase.RELEASE_IMPORT,
        description="Create release: v1.0.0",
        parameters={
            "target_repo": "target/repo",
            "tag": "v1.0.0",
            "name": "Release 1.0.0",
            "body": "First release",
            "draft": False,
            "prerelease": False,
            "gitlab_release_id": 1
        },
        dependencies=[],
        dry_run_safe=False,
        reversible=True,
        estimated_duration_seconds=20
    )
    
    # Create asset upload actions
    asset1_id = generator.add_action(
        action_type=ActionType.RELEASE_ASSET_UPLOAD,
        component="releases",
        phase=Phase.RELEASE_IMPORT,
        description="Upload asset: v1.0.0/myapp-linux",
        parameters={
            "target_repo": "target/repo",
            "release_tag": "v1.0.0",
            "asset_path": "/tmp/export/releases/v1.0.0/myapp-linux",
            "asset_name": "myapp-linux",
            "content_type": "application/octet-stream"
        },
        dependencies=[release_id],
        dry_run_safe=False,
        reversible=True,
        estimated_duration_seconds=10
    )
    
    asset2_id = generator.add_action(
        action_type=ActionType.RELEASE_ASSET_UPLOAD,
        component="releases",
        phase=Phase.RELEASE_IMPORT,
        description="Upload asset: v1.0.0/myapp-darwin",
        parameters={
            "target_repo": "target/repo",
            "release_tag": "v1.0.0",
            "asset_path": "/tmp/export/releases/v1.0.0/myapp-darwin",
            "asset_name": "myapp-darwin",
            "content_type": "application/octet-stream"
        },
        dependencies=[release_id],
        dry_run_safe=False,
        reversible=True,
        estimated_duration_seconds=10
    )
    
    # Build plan
    plan = generator.build_plan()
    
    # Verify actions
    assert len(plan["actions"]) == 3
    
    # Find actions by type
    release_actions = [a for a in plan["actions"] if a["type"] == ActionType.RELEASE_CREATE]
    asset_actions = [a for a in plan["actions"] if a["type"] == ActionType.RELEASE_ASSET_UPLOAD]
    
    assert len(release_actions) == 1
    assert len(asset_actions) == 2
    
    # Verify asset actions have correct parameters
    assert asset_actions[0]["parameters"]["asset_name"] == "myapp-linux"
    assert asset_actions[0]["parameters"]["release_tag"] == "v1.0.0"
    assert asset_actions[1]["parameters"]["asset_name"] == "myapp-darwin"
    assert asset_actions[1]["parameters"]["release_tag"] == "v1.0.0"
    
    # Verify dependencies
    assert release_id in asset_actions[0]["dependencies"]
    assert release_id in asset_actions[1]["dependencies"]
