"""
Plan Schema - Defines the structure and validation for migration plans.

Reference: docs/PLAN_SCHEMA.md
"""

from __future__ import annotations

from enum import Enum
from typing import Any, TypedDict


class ActionType(str, Enum):
    """All supported action types in the migration plan."""
    
    CREATE_REPOSITORY = "create_repository"
    PUSH_CODE = "push_code"
    PUSH_LFS = "push_lfs"
    CREATE_LABEL = "create_label"
    CREATE_MILESTONE = "create_milestone"
    CREATE_ISSUE = "create_issue"
    CREATE_PULL_REQUEST = "create_pull_request"
    ADD_ISSUE_COMMENT = "add_issue_comment"
    ADD_PR_COMMENT = "add_pr_comment"
    COMMIT_WORKFLOW = "commit_workflow"
    CREATE_ENVIRONMENT = "create_environment"
    SET_SECRET = "set_secret"
    SET_VARIABLE = "set_variable"
    PUSH_WIKI = "push_wiki"
    CREATE_RELEASE = "create_release"
    UPLOAD_RELEASE_ASSET = "upload_release_asset"
    PUBLISH_PACKAGE = "publish_package"
    SET_BRANCH_PROTECTION = "set_branch_protection"
    ADD_COLLABORATOR = "add_collaborator"
    CREATE_WEBHOOK = "create_webhook"
    COMMIT_PRESERVATION_ARTIFACTS = "commit_preservation_artifacts"


class PhaseType(str, Enum):
    """Phases for organizing actions in the migration plan."""
    
    REPOSITORY_CREATION = "repository_creation"
    CODE_PUSH = "code_push"
    LABELS_AND_MILESTONES = "labels_and_milestones"
    ISSUES_AND_PRS = "issues_and_prs"
    CICD_SETUP = "cicd_setup"
    WIKI_AND_RELEASES = "wiki_and_releases"
    SETTINGS_AND_PERMISSIONS = "settings_and_permissions"
    PRESERVATION_ARTIFACTS = "preservation_artifacts"


class Action(TypedDict, total=False):
    """A single action in the migration plan."""
    
    id: str  # Unique action ID
    action_type: str  # ActionType value
    idempotency_key: str  # Unique, deterministic key
    description: str  # Human-readable description
    phase: str  # PhaseType value
    dependencies: list[str]  # Action IDs this depends on
    parameters: dict[str, Any]  # Action-specific parameters
    requires_user_input: bool  # Whether user input is needed
    user_input_fields: list[dict[str, Any]]  # Fields requiring input


class Plan(TypedDict):
    """Complete migration plan."""
    
    version: str  # Plan schema version
    project_id: str  # Source project identifier
    run_id: str  # Unique run identifier
    generated_at: str  # ISO timestamp
    actions: list[Action]
    phases: dict[str, list[str]]  # Phase name -> action IDs
    statistics: dict[str, Any]


def validate_plan(plan: dict[str, Any]) -> bool:
    """
    Validate a migration plan against the schema.
    
    Args:
        plan: Plan dictionary to validate
        
    Returns:
        True if valid
        
    Raises:
        ValueError: If plan is invalid
    """
    required_fields = ["version", "project_id", "run_id", "generated_at", "actions", "phases", "statistics"]
    
    for field in required_fields:
        if field not in plan:
            raise ValueError(f"Missing required field: {field}")
    
    # Validate actions
    if not isinstance(plan["actions"], list):
        raise ValueError("actions must be a list")
    
    action_ids = set()
    idempotency_keys = set()
    
    for i, action in enumerate(plan["actions"]):
        # Check required action fields
        action_required = ["id", "action_type", "idempotency_key", "description", "phase"]
        for field in action_required:
            if field not in action:
                raise ValueError(f"Action {i} missing required field: {field}")
        
        # Check for duplicate IDs
        if action["id"] in action_ids:
            raise ValueError(f"Duplicate action ID: {action['id']}")
        action_ids.add(action["id"])
        
        # Check for duplicate idempotency keys
        if action["idempotency_key"] in idempotency_keys:
            raise ValueError(f"Duplicate idempotency key: {action['idempotency_key']}")
        idempotency_keys.add(action["idempotency_key"])
        
        # Validate action type
        try:
            ActionType(action["action_type"])
        except ValueError:
            raise ValueError(f"Invalid action type: {action['action_type']}")
        
        # Validate phase
        try:
            PhaseType(action["phase"])
        except ValueError:
            raise ValueError(f"Invalid phase: {action['phase']}")
        
        # Validate dependencies exist
        for dep_id in action.get("dependencies", []):
            if dep_id not in action_ids and dep_id not in [a["id"] for a in plan["actions"]]:
                # Allow forward references, will be validated later
                pass
    
    # Validate all dependencies exist
    all_action_ids = {action["id"] for action in plan["actions"]}
    for action in plan["actions"]:
        for dep_id in action.get("dependencies", []):
            if dep_id not in all_action_ids:
                raise ValueError(f"Action {action['id']} depends on non-existent action: {dep_id}")
    
    # Validate phases
    if not isinstance(plan["phases"], dict):
        raise ValueError("phases must be a dictionary")
    
    return True


def generate_idempotency_key(
    project_id: str,
    action_type: ActionType,
    entity_id: str,
    additional_data: str = ""
) -> str:
    """
    Generate a deterministic idempotency key for an action.
    
    Format: {project_id}:{action_type}:{entity_id}:{hash}
    
    Args:
        project_id: Project identifier
        action_type: Type of action
        entity_id: Entity identifier (e.g., issue number, label name)
        additional_data: Additional data to include in hash
        
    Returns:
        Idempotency key
    """
    import hashlib
    
    # Create deterministic hash
    hash_input = f"{project_id}:{action_type.value}:{entity_id}:{additional_data}"
    hash_value = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    
    return f"{project_id}:{action_type.value}:{entity_id}:{hash_value}"
