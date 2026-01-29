"""
Tests for plan generator.
"""

import pytest
from plan_agent.planner import PlanGenerator
from plan_agent.schema import ActionType, PhaseType


def create_simple_transform_output():
    """Create a simple transform output for testing."""
    return {
        "repository": {
            "name": "test-repo",
            "description": "Test repository",
            "visibility": "private",
            "default_branch": "main",
            "branches": ["main", "develop"],
            "has_lfs": False,
        },
        "labels": [
            {"name": "bug", "color": "d73a4a", "description": "Bug report"},
            {"name": "enhancement", "color": "a2eeef"},
        ],
        "milestones": [
            {"id": 1, "title": "v1.0", "description": "First release", "due_date": "2024-12-31"},
        ],
        "issues": [
            {
                "number": 1,
                "title": "Test issue",
                "body": "Test body",
                "labels": ["bug"],
                "comments": [],
            }
        ],
        "pull_requests": [],
        "workflows": [],
        "environments": [],
        "secrets": [],
        "variables": [],
        "wiki": {"enabled": False},
        "releases": [],
        "branch_protections": [],
        "collaborators": [],
        "webhooks": [],
    }


def test_plan_generator_initialization():
    """Test initializing the plan generator."""
    generator = PlanGenerator("test-project", "run-123")
    
    assert generator.project_id == "test-project"
    assert generator.run_id == "run-123"
    assert len(generator.actions) == 0


def test_add_action_basic():
    """Test adding a basic action."""
    generator = PlanGenerator("test-project", "run-123")
    
    action_id = generator.add_action(
        ActionType.CREATE_REPOSITORY,
        PhaseType.REPOSITORY_CREATION,
        "Create repository",
        {"name": "test-repo"},
        entity_id="repository"
    )
    
    assert action_id.startswith("action_")
    assert len(generator.actions) == 1
    assert generator.actions[0]["action_type"] == "create_repository"
    assert generator.actions[0]["phase"] == "repository_creation"


def test_add_action_with_dependencies():
    """Test adding actions with dependencies."""
    generator = PlanGenerator("test-project", "run-123")
    
    action1 = generator.add_action(
        ActionType.CREATE_REPOSITORY,
        PhaseType.REPOSITORY_CREATION,
        "Create repository",
        {},
        entity_id="repo"
    )
    
    action2 = generator.add_action(
        ActionType.PUSH_CODE,
        PhaseType.CODE_PUSH,
        "Push code",
        {},
        entity_id="code",
        dependencies=[action1]
    )
    
    assert len(generator.actions) == 2
    assert action1 in generator.actions[1]["dependencies"]


def test_add_action_user_input():
    """Test adding action requiring user input."""
    generator = PlanGenerator("test-project", "run-123")
    
    action_id = generator.add_action(
        ActionType.SET_SECRET,
        PhaseType.CICD_SETUP,
        "Set secret",
        {"name": "SECRET_KEY"},
        requires_user_input=True,
        user_input_fields=[{"name": "value", "description": "Secret value"}]
    )
    
    action = generator.actions[0]
    assert action["requires_user_input"] is True
    assert len(action["user_input_fields"]) == 1


def test_generate_from_transform_simple():
    """Test generating a plan from simple transform output."""
    transform_output = create_simple_transform_output()
    generator = PlanGenerator("test-project", "run-123")
    
    plan = generator.generate_from_transform(transform_output)
    
    assert plan["project_id"] == "test-project"
    assert plan["run_id"] == "run-123"
    assert plan["version"] == "1.0"
    assert len(plan["actions"]) > 0
    
    # Should have at least create_repository and push_code
    action_types = [a["action_type"] for a in plan["actions"]]
    assert "create_repository" in action_types
    assert "push_code" in action_types


def test_generate_from_transform_labels():
    """Test that labels are created from transform output."""
    transform_output = create_simple_transform_output()
    generator = PlanGenerator("test-project", "run-123")
    
    plan = generator.generate_from_transform(transform_output)
    
    label_actions = [a for a in plan["actions"] if a["action_type"] == "create_label"]
    assert len(label_actions) == 2
    assert label_actions[0]["parameters"]["name"] == "bug"
    assert label_actions[1]["parameters"]["name"] == "enhancement"


def test_generate_from_transform_issues():
    """Test that issues are created from transform output."""
    transform_output = create_simple_transform_output()
    generator = PlanGenerator("test-project", "run-123")
    
    plan = generator.generate_from_transform(transform_output)
    
    issue_actions = [a for a in plan["actions"] if a["action_type"] == "create_issue"]
    assert len(issue_actions) == 1
    assert issue_actions[0]["parameters"]["title"] == "Test issue"


def test_generate_from_transform_lfs():
    """Test LFS action is created when needed."""
    transform_output = create_simple_transform_output()
    transform_output["repository"]["has_lfs"] = True
    transform_output["repository"]["lfs_objects"] = ["file1.bin", "file2.bin"]
    
    generator = PlanGenerator("test-project", "run-123")
    plan = generator.generate_from_transform(transform_output)
    
    lfs_actions = [a for a in plan["actions"] if a["action_type"] == "push_lfs"]
    assert len(lfs_actions) == 1


def test_generate_from_transform_dependencies_correct():
    """Test that dependencies are correctly set."""
    transform_output = create_simple_transform_output()
    generator = PlanGenerator("test-project", "run-123")
    
    plan = generator.generate_from_transform(transform_output)
    
    # Find repo and code actions
    repo_action = next(a for a in plan["actions"] if a["action_type"] == "create_repository")
    code_action = next(a for a in plan["actions"] if a["action_type"] == "push_code")
    
    # Code should depend on repository
    assert repo_action["id"] in code_action["dependencies"]


def test_build_plan_statistics():
    """Test that plan statistics are calculated correctly."""
    transform_output = create_simple_transform_output()
    generator = PlanGenerator("test-project", "run-123")
    
    plan = generator.generate_from_transform(transform_output)
    stats = plan["statistics"]
    
    assert "total_actions" in stats
    assert "actions_by_type" in stats
    assert "actions_by_phase" in stats
    assert "actions_requiring_user_input" in stats
    assert stats["total_actions"] == len(plan["actions"])


def test_build_plan_phases_organized():
    """Test that actions are organized into phases."""
    transform_output = create_simple_transform_output()
    generator = PlanGenerator("test-project", "run-123")
    
    plan = generator.generate_from_transform(transform_output)
    
    # Check that all phases exist
    for phase in PhaseType:
        assert phase.value in plan["phases"]
    
    # Check that repository_creation phase has actions
    assert len(plan["phases"]["repository_creation"]) > 0


def test_get_user_inputs_required():
    """Test getting actions requiring user input."""
    generator = PlanGenerator("test-project", "run-123")
    
    generator.add_action(
        ActionType.CREATE_REPOSITORY,
        PhaseType.REPOSITORY_CREATION,
        "Create repo",
        {},
        requires_user_input=False
    )
    
    generator.add_action(
        ActionType.SET_SECRET,
        PhaseType.CICD_SETUP,
        "Set secret",
        {"name": "SECRET"},
        requires_user_input=True,
        user_input_fields=[{"name": "value", "description": "Secret value"}]
    )
    
    user_inputs = generator.get_user_inputs_required()
    assert len(user_inputs) == 1
    assert user_inputs[0]["action_type"] == "set_secret"


def test_generate_from_transform_full():
    """Test generating a plan with all feature types."""
    transform_output = {
        "repository": {
            "name": "full-repo",
            "description": "Full test",
            "visibility": "public",
            "default_branch": "main",
            "branches": ["main"],
            "has_lfs": True,
            "lfs_objects": ["file.bin"],
        },
        "labels": [{"name": "test", "color": "ffffff"}],
        "milestones": [{"id": 1, "title": "M1"}],
        "issues": [{"number": 1, "title": "Issue 1", "comments": [{"id": 1, "body": "Comment"}]}],
        "pull_requests": [{"number": 1, "title": "PR 1", "head": "feature", "base": "main", "comments": []}],
        "workflows": [{"name": "ci.yml", "path": ".github/workflows/ci.yml", "content": "..."}],
        "environments": [{"name": "production"}],
        "secrets": [{"name": "SECRET_KEY"}],
        "variables": [{"name": "VAR", "value": "value"}],
        "wiki": {"enabled": True, "pages": []},
        "releases": [{"tag_name": "v1.0", "assets": [{"name": "asset.zip", "path": "/tmp/asset.zip"}]}],
        "branch_protections": [{"branch": "main"}],
        "collaborators": [{"username": "user1"}],
        "webhooks": [{"url": "https://example.com/hook"}],
        "preservation_artifacts": {"metadata": "..."},
    }
    
    generator = PlanGenerator("test-project", "run-123")
    plan = generator.generate_from_transform(transform_output)
    
    # Check that we have actions for each feature
    action_types = {a["action_type"] for a in plan["actions"]}
    
    expected_types = {
        "create_repository",
        "push_code",
        "push_lfs",
        "create_label",
        "create_milestone",
        "create_issue",
        "add_issue_comment",
        "create_pull_request",
        "commit_workflow",
        "create_environment",
        "set_secret",
        "set_variable",
        "push_wiki",
        "create_release",
        "upload_release_asset",
        "set_branch_protection",
        "add_collaborator",
        "create_webhook",
        "commit_preservation_artifacts",
    }
    
    assert expected_types.issubset(action_types)


def test_idempotency_keys_unique():
    """Test that all idempotency keys are unique."""
    transform_output = create_simple_transform_output()
    generator = PlanGenerator("test-project", "run-123")
    
    plan = generator.generate_from_transform(transform_output)
    
    idempotency_keys = [a["idempotency_key"] for a in plan["actions"]]
    assert len(idempotency_keys) == len(set(idempotency_keys))


def test_circular_dependency_detection():
    """Test that circular dependencies are detected during plan build."""
    generator = PlanGenerator("test-project", "run-123")
    
    # Manually create a circular dependency
    action1 = generator.add_action(
        ActionType.CREATE_REPOSITORY,
        PhaseType.REPOSITORY_CREATION,
        "Action 1",
        {}
    )
    
    action2 = generator.add_action(
        ActionType.PUSH_CODE,
        PhaseType.CODE_PUSH,
        "Action 2",
        {},
        dependencies=[action1]
    )
    
    # Manually add a circular dependency (this is just for testing)
    generator.dependency_graph.add_dependency(action1, action2)
    
    with pytest.raises(ValueError, match="Circular dependency detected"):
        generator.build_plan()
