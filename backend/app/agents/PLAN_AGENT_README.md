# Plan Agent

The Plan Agent generates executable migration plans from transform outputs. It creates a complete, ordered list of actions needed to recreate a GitLab project on GitHub.

## Overview

The Plan Agent is Phase 5 of the gl2gh migration pipeline:
1. Discovery Agent - Scan GitLab
2. Export Agent - Export data
3. Transform Agent - Convert to GitHub format
4. **Plan Agent** - Generate execution plan ← You are here
5. Apply Agent - Execute on GitHub
6. Verify Agent - Validate results

## Features

### Action Generation
- **28+ action types** across 11 phases
- Deterministic idempotency keys for safe retries
- Dependency tracking and validation
- Topological sort for correct execution order

### Action Types Supported

#### Repository (Phase 1: Foundation)
- `repo_create` - Create GitHub repository
- `repo_push` - Push git bundle
- `repo_configure` - Update repository settings
- `lfs_configure` - Set up Git LFS

#### CI/CD (Phase 2: CI Setup)
- `workflow_commit` - Commit workflow file
- `environment_create` - Create environment
- `secret_set` - Set secret
- `variable_set` - Set variable
- `schedule_create` - Create workflow schedule

#### Issues (Phases 3-4: Issue Setup & Import)
- `label_create` - Create label
- `milestone_create` - Create milestone
- `issue_create` - Import issue

#### Pull Requests (Phase 5: PR Import)
- `pr_create` - Import merge request as PR
- `pr_comment_add` - Add comment to PR

#### Wiki (Phase 6: Wiki Import)
- `wiki_push` - Push wiki repository
- `wiki_commit` - Commit to docs folder

#### Releases (Phase 7: Release Import)
- `release_create` - Create release
- `release_asset_upload` - Upload release asset

#### Packages (Phase 8: Package Import)
- `package_publish` - Publish package to GHCR

#### Settings (Phase 9: Governance)
- `protection_set` - Set branch protection
- `collaborator_add` - Add collaborator
- `team_create` - Create team
- `codeowners_commit` - Commit CODEOWNERS file

#### Webhooks (Phase 10: Integrations)
- `webhook_create` - Create webhook
- `webhook_configure` - Configure webhook

#### Preservation (Phase 11: Preservation)
- `artifact_commit` - Commit preservation artifacts

### Dependency Management
- Automatic dependency calculation
- Circular dependency detection
- Topological sorting for execution order
- Validation before plan generation

### User Input Detection
Identifies actions requiring user input:
- Masked secrets (values not retrievable from GitLab)
- User mapping confirmations (low confidence matches)
- Repository configuration (name, visibility)

### Idempotency
- Deterministic key generation: `{action_type}-{entity_id}-{hash}`
- Same input always produces same key
- Enables safe retries and resume support

## Usage

```python
from app.agents.plan_agent import PlanAgent

# Create agent
agent = PlanAgent()

# Prepare inputs
inputs = {
    "output_dir": "artifacts/runs/run-001/plan",
    "run_id": "run-001",
    "project_id": "proj-001",
    "gitlab_project": "namespace/project",
    "github_target": "org/repo",
    "export_data": export_data,      # From Export Agent
    "transform_data": transform_data  # From Transform Agent
}

# Generate plan
result = await agent.execute(inputs)

if result["status"] == "success":
    plan = result["outputs"]["plan"]
    print(f"Generated {len(plan['actions'])} actions")
```

## Output Artifacts

The Plan Agent generates 5 artifacts:

### 1. plan.json (Machine-readable)
Complete plan with all actions, dependencies, and metadata.

```json
{
  "version": "1.0",
  "run_id": "run-001",
  "gitlab_project": "namespace/project",
  "github_target": "org/repo",
  "summary": {
    "total_actions": 156,
    "estimated_duration_minutes": 45,
    "requires_user_input": true
  },
  "actions": [...],
  "phases": [...],
  "validation": {...}
}
```

### 2. plan.md (Human-readable)
Markdown summary for easy review.

```markdown
# Migration Plan Summary

**Source**: namespace/project
**Target**: org/repo

## Overview
- Total Actions: 156
- Estimated Duration: 45 minutes
- Requires User Input: Yes

## Execution Phases
1. Foundation (3 actions)
2. CI Setup (15 actions)
...
```

### 3. dependency_graph.json
Action dependency mapping for debugging.

```json
{
  "action-001": [],
  "action-002": ["action-001"],
  "action-003": ["action-001", "action-002"]
}
```

### 4. user_inputs_required.json
List of required user inputs.

```json
[
  {
    "type": "secret_value",
    "key": "DATABASE_URL",
    "scope": "repository",
    "reason": "GitLab variable was masked",
    "required": true
  }
]
```

### 5. plan_stats.json
Statistics and metrics.

```json
{
  "total_actions": 156,
  "actions_by_type": {
    "repo_create": 1,
    "issue_create": 45,
    ...
  },
  "actions_by_phase": {
    "foundation": 3,
    "issue_import": 45,
    ...
  }
}
```

## Architecture

### PlanGenerator
Core plan generation logic:
- Action creation with automatic ID assignment
- Idempotency key generation
- Dependency graph building
- Topological sorting
- Phase organization

### PlanAgent
BaseAgent implementation:
- Input validation
- Calls PlanGenerator
- Generates all output artifacts
- Error handling and logging

## Validation

The Plan Agent performs comprehensive validation:

1. **Dependency Validation**
   - All referenced actions exist
   - No circular dependencies
   - Dependencies are resolvable

2. **Idempotency Validation**
   - No duplicate keys
   - Keys are deterministic

3. **User Input Validation**
   - Required inputs are flagged
   - Fallback options provided

## Testing

Run the test suite:

```bash
cd backend
pytest tests/test_plan_agent.py -v
```

Test coverage:
- Plan generation with various data combinations
- Dependency graph validation
- Circular dependency detection
- Topological sorting
- Idempotency key generation
- User input detection
- Artifact generation

## Examples

### Minimal Plan (Repository only)
```python
export_data = {}
transform_data = {}
# Generates: repo_create + repo_push (2 actions)
```

### Full Migration
```python
export_data = {
    "labels": [...],
    "issues": [...],
    "merge_requests": [...],
    "releases": [...],
    "webhooks": [...]
}
transform_data = {
    "workflows": [...],
    "environments": [...],
    "branch_protections": [...]
}
# Generates: 100+ actions across all phases
```

## Integration

The Plan Agent integrates with:
- **Orchestrator**: Called in sequence after Transform Agent
- **Apply Agent**: Consumes plan.json for execution
- **Verify Agent**: Uses plan for validation expectations

## Design Principles

1. **Deterministic**: Same inputs always produce same plan
2. **Idempotent**: Actions can be safely retried
3. **Safe**: Validates before execution
4. **Resumable**: Supports checkpoint and resume
5. **Documented**: Human-readable output included

## References

- [PLAN_SCHEMA.md](../../docs/PLAN_SCHEMA.md) - Complete schema documentation
- [BaseAgent](./base_agent.py) - Agent framework base class
- [TransformAgent](./transform_agent.py) - Previous phase in pipeline
- [ApplyAgent](./apply_agent.py) - Next phase in pipeline
