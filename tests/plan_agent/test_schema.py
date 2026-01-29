"""
Tests for plan schema and validation.
"""

import pytest
from plan_agent.schema import (
    ActionType,
    PhaseType,
    generate_idempotency_key,
    validate_plan,
)


def test_action_types_complete():
    """Test that all 21 action types are defined."""
    expected_types = {
        "create_repository",
        "push_code",
        "push_lfs",
        "create_label",
        "create_milestone",
        "create_issue",
        "create_pull_request",
        "add_issue_comment",
        "add_pr_comment",
        "commit_workflow",
        "create_environment",
        "set_secret",
        "set_variable",
        "push_wiki",
        "create_release",
        "upload_release_asset",
        "publish_package",
        "set_branch_protection",
        "add_collaborator",
        "create_webhook",
        "commit_preservation_artifacts",
    }
    
    actual_types = {at.value for at in ActionType}
    assert actual_types == expected_types


def test_phase_types_complete():
    """Test that all 8 phases are defined."""
    expected_phases = {
        "repository_creation",
        "code_push",
        "labels_and_milestones",
        "issues_and_prs",
        "cicd_setup",
        "wiki_and_releases",
        "settings_and_permissions",
        "preservation_artifacts",
    }
    
    actual_phases = {pt.value for pt in PhaseType}
    assert actual_phases == expected_phases


def test_idempotency_key_deterministic():
    """Test that idempotency keys are deterministic."""
    key1 = generate_idempotency_key(
        "project123",
        ActionType.CREATE_ISSUE,
        "issue_42",
        "additional_data"
    )
    key2 = generate_idempotency_key(
        "project123",
        ActionType.CREATE_ISSUE,
        "issue_42",
        "additional_data"
    )
    
    assert key1 == key2
    assert key1.startswith("project123:create_issue:issue_42:")


def test_idempotency_key_unique_per_input():
    """Test that different inputs produce different keys."""
    key1 = generate_idempotency_key(
        "project123",
        ActionType.CREATE_ISSUE,
        "issue_42",
        "data1"
    )
    key2 = generate_idempotency_key(
        "project123",
        ActionType.CREATE_ISSUE,
        "issue_42",
        "data2"
    )
    
    assert key1 != key2


def test_validate_plan_valid():
    """Test validation of a valid plan."""
    plan = {
        "version": "1.0",
        "project_id": "test-project",
        "run_id": "run-123",
        "generated_at": "2024-01-01T00:00:00Z",
        "actions": [
            {
                "id": "action_001",
                "action_type": "create_repository",
                "idempotency_key": "test:create_repository:repo:abc123",
                "description": "Create repository",
                "phase": "repository_creation",
                "dependencies": [],
                "parameters": {},
                "requires_user_input": False,
            }
        ],
        "phases": {
            "repository_creation": ["action_001"]
        },
        "statistics": {
            "total_actions": 1
        }
    }
    
    assert validate_plan(plan) is True


def test_validate_plan_missing_field():
    """Test validation fails with missing required field."""
    plan = {
        "version": "1.0",
        "project_id": "test-project",
        # Missing run_id
        "generated_at": "2024-01-01T00:00:00Z",
        "actions": [],
        "phases": {},
        "statistics": {}
    }
    
    with pytest.raises(ValueError, match="Missing required field: run_id"):
        validate_plan(plan)


def test_validate_plan_duplicate_action_id():
    """Test validation fails with duplicate action IDs."""
    plan = {
        "version": "1.0",
        "project_id": "test-project",
        "run_id": "run-123",
        "generated_at": "2024-01-01T00:00:00Z",
        "actions": [
            {
                "id": "action_001",
                "action_type": "create_repository",
                "idempotency_key": "test:create_repository:repo:abc123",
                "description": "Create repository",
                "phase": "repository_creation",
                "dependencies": [],
                "parameters": {},
            },
            {
                "id": "action_001",  # Duplicate
                "action_type": "push_code",
                "idempotency_key": "test:push_code:code:xyz789",
                "description": "Push code",
                "phase": "code_push",
                "dependencies": [],
                "parameters": {},
            }
        ],
        "phases": {},
        "statistics": {}
    }
    
    with pytest.raises(ValueError, match="Duplicate action ID"):
        validate_plan(plan)


def test_validate_plan_duplicate_idempotency_key():
    """Test validation fails with duplicate idempotency keys."""
    plan = {
        "version": "1.0",
        "project_id": "test-project",
        "run_id": "run-123",
        "generated_at": "2024-01-01T00:00:00Z",
        "actions": [
            {
                "id": "action_001",
                "action_type": "create_repository",
                "idempotency_key": "test:create_repository:repo:same",
                "description": "Create repository",
                "phase": "repository_creation",
                "dependencies": [],
                "parameters": {},
            },
            {
                "id": "action_002",
                "action_type": "push_code",
                "idempotency_key": "test:create_repository:repo:same",  # Duplicate
                "description": "Push code",
                "phase": "code_push",
                "dependencies": [],
                "parameters": {},
            }
        ],
        "phases": {},
        "statistics": {}
    }
    
    with pytest.raises(ValueError, match="Duplicate idempotency key"):
        validate_plan(plan)


def test_validate_plan_invalid_action_type():
    """Test validation fails with invalid action type."""
    plan = {
        "version": "1.0",
        "project_id": "test-project",
        "run_id": "run-123",
        "generated_at": "2024-01-01T00:00:00Z",
        "actions": [
            {
                "id": "action_001",
                "action_type": "invalid_action",  # Invalid
                "idempotency_key": "test:invalid:repo:abc123",
                "description": "Invalid action",
                "phase": "repository_creation",
                "dependencies": [],
                "parameters": {},
            }
        ],
        "phases": {},
        "statistics": {}
    }
    
    with pytest.raises(ValueError, match="Invalid action type"):
        validate_plan(plan)


def test_validate_plan_missing_dependency():
    """Test validation fails when dependency doesn't exist."""
    plan = {
        "version": "1.0",
        "project_id": "test-project",
        "run_id": "run-123",
        "generated_at": "2024-01-01T00:00:00Z",
        "actions": [
            {
                "id": "action_001",
                "action_type": "push_code",
                "idempotency_key": "test:push_code:code:abc123",
                "description": "Push code",
                "phase": "code_push",
                "dependencies": ["action_999"],  # Doesn't exist
                "parameters": {},
            }
        ],
        "phases": {},
        "statistics": {}
    }
    
    with pytest.raises(ValueError, match="depends on non-existent action"):
        validate_plan(plan)
