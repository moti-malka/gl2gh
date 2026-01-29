# Plan Schema Documentation

## Overview

The Plan Agent generates a comprehensive migration plan that defines all actions needed to recreate a GitLab project on GitHub. This document describes the plan schema and structure.

## Plan Structure

```json
{
  "version": "1.0",
  "project_id": "string",
  "run_id": "string",
  "generated_at": "ISO8601 timestamp",
  "actions": [...],
  "phases": {...},
  "statistics": {...}
}
```

### Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `version` | string | Schema version (currently "1.0") |
| `project_id` | string | Source project identifier |
| `run_id` | string | Unique run identifier |
| `generated_at` | string | ISO 8601 timestamp when plan was generated |
| `actions` | array | List of all migration actions (ordered by dependencies) |
| `phases` | object | Actions organized by execution phase |
| `statistics` | object | Summary statistics about the plan |

## Actions

Each action represents a single migration step with the following structure:

```json
{
  "id": "action_0001_create_repository_repository",
  "action_type": "create_repository",
  "idempotency_key": "project123:create_repository:repository:abc123def456",
  "description": "Create GitHub repository for project123",
  "phase": "repository_creation",
  "dependencies": [],
  "parameters": {
    "name": "my-repo",
    "description": "Repository description",
    "visibility": "private"
  },
  "requires_user_input": false,
  "user_input_fields": []
}
```

### Action Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique action identifier |
| `action_type` | string | Yes | Type of action (see Action Types below) |
| `idempotency_key` | string | Yes | Deterministic key for idempotent execution |
| `description` | string | Yes | Human-readable description |
| `phase` | string | Yes | Execution phase (see Phases below) |
| `dependencies` | array | Yes | List of action IDs this action depends on |
| `parameters` | object | Yes | Action-specific parameters |
| `requires_user_input` | boolean | No | Whether user input is required |
| `user_input_fields` | array | No | Fields requiring user input |

## Action Types

The plan supports 21 action types organized into 8 phases:

### Phase 1: Repository Creation
- **`create_repository`**: Create a new GitHub repository

### Phase 2: Code Push
- **`push_code`**: Push repository code and branches
- **`push_lfs`**: Push Git LFS objects

### Phase 3: Labels and Milestones
- **`create_label`**: Create an issue/PR label
- **`create_milestone`**: Create a milestone

### Phase 4: Issues and PRs
- **`create_issue`**: Create an issue
- **`create_pull_request`**: Create a pull request
- **`add_issue_comment`**: Add a comment to an issue
- **`add_pr_comment`**: Add a comment to a PR

### Phase 5: CI/CD Setup
- **`commit_workflow`**: Commit a GitHub Actions workflow file
- **`create_environment`**: Create a deployment environment
- **`set_secret`**: Set a repository/environment secret
- **`set_variable`**: Set a repository/environment variable

### Phase 6: Wiki and Releases
- **`push_wiki`**: Push wiki content
- **`create_release`**: Create a release
- **`upload_release_asset`**: Upload an asset to a release
- **`publish_package`**: Publish a package

### Phase 7: Settings and Permissions
- **`set_branch_protection`**: Configure branch protection rules
- **`add_collaborator`**: Add a collaborator to the repository
- **`create_webhook`**: Create a webhook

### Phase 8: Preservation Artifacts
- **`commit_preservation_artifacts`**: Commit GitLab-specific preservation data

## Phases

Actions are organized into 8 sequential phases:

```json
{
  "phases": {
    "repository_creation": ["action_0001_create_repository_repository"],
    "code_push": ["action_0002_push_code_code", "action_0003_push_lfs_lfs"],
    "labels_and_milestones": ["action_0004_create_label_bug", ...],
    "issues_and_prs": ["action_0010_create_issue_1", ...],
    "cicd_setup": ["action_0050_commit_workflow_ci", ...],
    "wiki_and_releases": ["action_0100_create_release_v1.0", ...],
    "settings_and_permissions": ["action_0150_set_branch_protection_main", ...],
    "preservation_artifacts": ["action_0200_commit_preservation_artifacts_preservation"]
  }
}
```

Phases are executed sequentially, but actions within a phase can potentially be executed in parallel (subject to their individual dependencies).

## Idempotency Keys

Each action has a deterministic idempotency key with the format:

```
{project_id}:{action_type}:{entity_id}:{hash}
```

Example:
```
project123:create_issue:issue_42:a1b2c3d4e5f6g7h8
```

The hash is computed from the action parameters to ensure uniqueness while maintaining determinism (same input always produces the same key).

## Dependencies

Actions can depend on other actions. The dependency graph ensures:

1. **Acyclic**: No circular dependencies
2. **Topologically sorted**: Actions are ordered so dependencies come first
3. **Valid references**: All dependency IDs exist in the plan

Example dependency chain:
```
create_repository
  └─> push_code
       ├─> create_issue
       └─> create_pull_request
```

## Statistics

The plan includes summary statistics:

```json
{
  "statistics": {
    "total_actions": 142,
    "actions_by_type": {
      "create_repository": 1,
      "create_issue": 50,
      "create_label": 10,
      ...
    },
    "actions_by_phase": {
      "repository_creation": 1,
      "code_push": 2,
      "issues_and_prs": 75,
      ...
    },
    "actions_requiring_user_input": 5,
    "total_dependencies": 200
  }
}
```

## User Input Requirements

Some actions require user input (e.g., secrets, webhook secrets). These actions have:

```json
{
  "requires_user_input": true,
  "user_input_fields": [
    {
      "name": "value",
      "description": "The secret value"
    }
  ]
}
```

A separate `user_inputs_required.json` file lists all such actions for easy identification.

## Output Files

The plan agent generates the following files in `artifacts/{run_id}/plan/`:

### `plan.json`
Complete machine-readable plan with all actions, dependencies, and metadata.

### `plan.md`
Human-readable Markdown summary showing:
- Statistics
- Actions organized by phase
- User input requirements
- Dependency information

### `dependency_graph.json`
Graph structure with nodes and edges for visualization:

```json
{
  "nodes": ["action_001", "action_002", ...],
  "edges": [
    {"from": "action_002", "to": "action_001"},
    ...
  ]
}
```

### `user_inputs_required.json`
List of actions requiring user input:

```json
{
  "user_inputs_required": [
    {
      "action_id": "action_050_set_secret_API_KEY",
      "action_type": "set_secret",
      "description": "Set secret: API_KEY",
      "user_input_fields": [...]
    }
  ]
}
```

### `plan_stats.json`
Statistics from the plan for quick reference.

## Validation Rules

A valid plan must satisfy:

1. All required top-level fields are present
2. All actions have required fields
3. No duplicate action IDs
4. No duplicate idempotency keys
5. All action types are valid
6. All phases are valid
7. All dependency references are valid
8. Dependency graph is acyclic

## Example Action Parameters

### create_repository
```json
{
  "name": "my-repo",
  "description": "Repository description",
  "visibility": "private"
}
```

### push_code
```json
{
  "branches": ["main", "develop", "feature/x"],
  "default_branch": "main"
}
```

### create_issue
```json
{
  "title": "Issue title",
  "body": "Issue body",
  "labels": ["bug", "priority-high"],
  "milestone": "v1.0",
  "assignees": ["user1", "user2"]
}
```

### set_branch_protection
```json
{
  "branch": "main",
  "required_reviews": 2,
  "require_code_owner_reviews": true,
  "dismiss_stale_reviews": true,
  "require_status_checks": ["ci", "tests"]
}
```

### create_webhook
```json
{
  "url": "https://example.com/webhook",
  "events": ["push", "pull_request"],
  "content_type": "json"
}
```

## Usage

### Generate a Plan

```bash
python -m plan_agent \
  --transform-output ./transform_output.json \
  --project-id my-gitlab-project \
  --run-id run-2024-01-15-123456 \
  --output-dir ./artifacts
```

### Validate a Plan

```bash
python -m plan_agent \
  --transform-output ./transform_output.json \
  --project-id my-gitlab-project \
  --run-id run-2024-01-15-123456 \
  --validate-only
```

### Programmatic Usage

```python
from plan_agent import PlanGenerator, validate_plan

# Load transform output
with open("transform_output.json") as f:
    transform_output = json.load(f)

# Generate plan
generator = PlanGenerator("my-project", "run-123")
plan = generator.generate_from_transform(transform_output)

# Validate
validate_plan(plan)

# Get user inputs needed
user_inputs = generator.get_user_inputs_required()
```

## Version History

### Version 1.0 (Current)
- Initial plan schema
- 21 action types
- 8 execution phases
- Dependency graph support
- User input identification
- Idempotency keys
