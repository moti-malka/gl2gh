# Plan Agent

The Plan Agent generates comprehensive, ordered migration plans from transform outputs. It creates a complete execution plan that defines all actions needed to recreate a GitLab project on GitHub.

## Features

- **21 Action Types**: Covers all aspects of migration (repository, code, issues, PRs, CI/CD, wiki, releases, settings)
- **8 Execution Phases**: Actions organized into logical phases
- **Dependency Management**: Automatic dependency tracking and topological sorting
- **Circular Dependency Detection**: Validates that the plan is acyclic
- **Idempotent Keys**: Deterministic keys for safe re-execution
- **User Input Identification**: Flags actions requiring manual input (secrets, webhooks)
- **Multiple Output Formats**: JSON (machine-readable) and Markdown (human-readable)

## Installation

The plan agent is part of the gl2gh project:

```bash
cd gl2gh
pip install -e .
```

## Usage

### Command Line

Generate a migration plan from transform output:

```bash
python -m plan_agent \
  --transform-output ./transform_output.json \
  --project-id my-gitlab-project \
  --run-id run-2024-01-15-123456 \
  --output-dir ./artifacts
```

This will create:
```
artifacts/run-2024-01-15-123456/plan/
├── plan.json                      # Complete machine-readable plan
├── plan.md                        # Human-readable summary
├── dependency_graph.json          # Dependency graph structure
├── user_inputs_required.json      # Actions requiring user input
└── plan_stats.json               # Summary statistics
```

### Validate Only

To validate a plan without saving outputs:

```bash
python -m plan_agent \
  --transform-output ./transform_output.json \
  --project-id my-gitlab-project \
  --run-id run-test \
  --validate-only
```

### Programmatic Usage

```python
from plan_agent import PlanGenerator, validate_plan
import json

# Load transform output
with open("transform_output.json") as f:
    transform_output = json.load(f)

# Generate plan
generator = PlanGenerator("my-project", "run-123")
plan = generator.generate_from_transform(transform_output)

# Validate
validate_plan(plan)

# Get actions requiring user input
user_inputs = generator.get_user_inputs_required()

# Save outputs
from plan_agent.output_generator import save_plan_outputs
from pathlib import Path

output_dir = Path("./artifacts/run-123/plan")
save_plan_outputs(plan, output_dir, generator.dependency_graph)
```

## Input Format

The plan agent expects transform output in the following format:

```json
{
  "repository": {
    "name": "repo-name",
    "description": "...",
    "visibility": "private",
    "default_branch": "main",
    "branches": ["main", "develop"],
    "has_lfs": false
  },
  "labels": [
    {"name": "bug", "color": "d73a4a", "description": "..."}
  ],
  "milestones": [
    {"id": 1, "title": "v1.0", "description": "..."}
  ],
  "issues": [
    {"number": 1, "title": "...", "body": "...", "comments": [...]}
  ],
  "pull_requests": [
    {"number": 1, "title": "...", "head": "...", "base": "...", "comments": [...]}
  ],
  "workflows": [
    {"name": "ci.yml", "path": ".github/workflows/ci.yml", "content": "..."}
  ],
  "environments": [{"name": "production"}],
  "secrets": [{"name": "API_KEY"}],
  "variables": [{"name": "NODE_ENV", "value": "production"}],
  "wiki": {"enabled": true, "pages": [...]},
  "releases": [{"tag_name": "v1.0", "assets": [...]}],
  "branch_protections": [{"branch": "main", ...}],
  "collaborators": [{"username": "user1", "permission": "push"}],
  "webhooks": [{"url": "https://...", "events": [...]}],
  "preservation_artifacts": {...}
}
```

See `examples/transform_output_example.json` for a complete example.

## Action Types

The plan supports 21 action types organized into 8 phases:

### Phase 1: Repository Creation
- `create_repository`: Create a new GitHub repository

### Phase 2: Code Push
- `push_code`: Push repository code and branches
- `push_lfs`: Push Git LFS objects

### Phase 3: Labels and Milestones
- `create_label`: Create an issue/PR label
- `create_milestone`: Create a milestone

### Phase 4: Issues and PRs
- `create_issue`: Create an issue
- `create_pull_request`: Create a pull request
- `add_issue_comment`: Add a comment to an issue
- `add_pr_comment`: Add a comment to a PR

### Phase 5: CI/CD Setup
- `commit_workflow`: Commit a GitHub Actions workflow
- `create_environment`: Create a deployment environment
- `set_secret`: Set a secret (requires user input)
- `set_variable`: Set a variable

### Phase 6: Wiki and Releases
- `push_wiki`: Push wiki content
- `create_release`: Create a release
- `upload_release_asset`: Upload an asset to a release
- `publish_package`: Publish a package

### Phase 7: Settings and Permissions
- `set_branch_protection`: Configure branch protection
- `add_collaborator`: Add a collaborator
- `create_webhook`: Create a webhook (requires user input)

### Phase 8: Preservation Artifacts
- `commit_preservation_artifacts`: Commit GitLab-specific data

## Dependency Management

The plan agent automatically:

1. **Tracks Dependencies**: Each action declares its dependencies
2. **Validates Acyclicity**: Ensures no circular dependencies exist
3. **Topological Sort**: Orders actions so dependencies execute first
4. **Generates Dependency Graph**: Creates a visual representation

Example dependency chain:
```
create_repository
  └─> push_code
       ├─> create_issue
       ├─> create_pull_request
       └─> create_release
```

## Idempotency

Each action has a deterministic idempotency key:

```
{project_id}:{action_type}:{entity_id}:{hash}
```

Example:
```
my-project:create_issue:issue_42:a1b2c3d4e5f6g7h8
```

The hash ensures uniqueness while maintaining determinism—the same input always produces the same key.

## User Input Requirements

Some actions require user input before execution:

- **Secrets**: `set_secret` (requires secret value)
- **Webhooks**: `create_webhook` (requires webhook secret)
- **Environments**: `create_environment` (requires protection rules)

The plan identifies these actions and generates `user_inputs_required.json` for easy reference.

## Testing

Run the test suite:

```bash
pytest tests/plan_agent/ -v
```

Test coverage includes:
- Schema validation (21 action types, 8 phases)
- Dependency graph operations (topological sort, cycle detection)
- Plan generation from transform outputs
- Idempotency key generation
- User input identification

## Example

Generate a plan from the included example:

```bash
python -m plan_agent \
  --transform-output examples/transform_output_example.json \
  --project-id example-project \
  --run-id run-example-001 \
  --output-dir ./artifacts

# Check the generated plan
cat artifacts/run-example-001/plan/plan.md
```

## Documentation

See [docs/PLAN_SCHEMA.md](../docs/PLAN_SCHEMA.md) for complete schema documentation.

## Architecture

```
plan_agent/
├── __init__.py              # Package exports
├── __main__.py              # CLI entry point
├── schema.py                # Action types, phases, validation
├── dependency_graph.py      # Dependency management
├── planner.py               # Plan generation logic
└── output_generator.py      # Output file generation
```

## License

MIT License - see LICENSE file for details.
