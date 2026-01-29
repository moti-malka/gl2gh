# GitLab Discovery Agent

A local MVP "Discovery Agent" for GitLab → GitHub migration planning. This tool scans GitLab groups and produces an inventory and readiness report for each project.

> **Note:** This is a discovery-only tool. It performs **no write operations** and makes no changes to GitLab or GitHub.

## Features

- 🔍 **Deep Group Scanning**: Recursively scans all subgroups under a root group
- 🌐 **Full Instance Discovery**: Optionally scan ALL accessible groups (no root-group required)
- 📊 **Project Inventory**: Collects detailed information about each project
- ✅ **Migration Readiness Assessment**: Evaluates complexity and identifies blockers
- 🔄 **CI/CD Detection**: Identifies projects with GitLab CI configuration
- 📦 **LFS Detection**: Detects Git LFS usage
- 📈 **Issue & MR Counts**: Gathers counts of merge requests and issues
- 🎯 **Deep Migration Scoring**: Calculates work scores (0-100) and buckets (S/M/L/XL) with `--deep`
- 🖥️ **Web Dashboard**: Visual interface for exploring scan results
- 🛡️ **Safe Operation**: Only GET requests, no modifications
- ⏱️ **Rate Limit Handling**: Exponential backoff and Retry-After support
- 📄 **JSON Output**: Deterministic, schema-validated output

## Requirements

- Python 3.10+
- GitLab Personal Access Token with appropriate scopes

### Required Token Scopes

| Scope | Purpose |
|-------|---------|
| `read_api` | List groups, projects, merge requests, issues |
| `read_repository` | Read `.gitlab-ci.yml`, `.gitattributes` files |

## Installation

```bash
# Clone or download this project
cd gl2gh

# Install dependencies (recommended: use a virtual environment)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package
pip install -e ".[dev]"
```

Or install dependencies only:

```bash
pip install requests python-dotenv jsonschema
pip install pytest pytest-mock responses  # For development
```

## Usage

### Scan a Specific Group

```bash
python -m discovery_agent \
  --base-url https://gitlab.com \
  --token glpat-xxxxxxxxxxxxxxxxxxxx \
  --root-group my-organization \
  --out ./output
```

### Scan ALL Accessible Groups

Omit `--root-group` to discover all groups you have access to:

```bash
python -m discovery_agent \
  --base-url https://gitlab.com \
  --token glpat-xxxxxxxxxxxxxxxxxxxx \
  --out ./output
```

### Using Environment Variables

Create a `.env` file in your working directory:

```bash
# .env
GITLAB_BASE_URL=https://gitlab.com
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
# GITLAB_ROOT_GROUP=my-organization  # Optional - omit to scan ALL groups
OUTPUT_DIR=./output
```

Then run:

```bash
python -m discovery_agent
```

### All CLI Options

```
usage: discovery_agent [-h] [--version] [--base-url URL] [--token TOKEN]
                       [--root-group GROUP] [--out DIR] [--max-api-calls N]
                       [--max-per-project-calls N] [-v] [-q]

GitLab Discovery Agent - Scan GitLab groups and produce migration readiness reports

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  --base-url URL        GitLab instance URL (e.g., https://gitlab.com)
  --token TOKEN         Personal Access Token for authentication
  --root-group GROUP    Root group to scan. If omitted, scans ALL accessible groups.
  --out DIR             Output directory for inventory.json (default: ./output)
  --max-api-calls N     Maximum total API calls (default: 5000)
  --max-per-project-calls N
                        Maximum API calls per project (default: 200)
  --deep                Enable deep analysis with migration scoring per project
  --deep-top-n N        Limit deep analysis to top N projects (default: 20, 0=all)
  -v, --verbose         Enable verbose (debug) logging
  -q, --quiet           Suppress all output except errors
```

### Deep Analysis Mode

Enable deep analysis with `--deep` to get detailed migration effort estimates per project:

```bash
python -m discovery_agent --deep --deep-top-n 50
```

Deep analysis provides:
- **Repository Profile**: Branch/tag counts, submodules, LFS detection
- **CI/CD Profile**: Parses `.gitlab-ci.yml` to detect features (includes, services, DAG, triggers, etc.)
- **Migration Estimate**: Work score (0-100), bucket (S/M/L/XL), and contributing factors

### Web Dashboard

View scan results in an interactive web dashboard:

```bash
python -m discovery_agent serve --port 8080 --dir ./output
```

Open http://localhost:8080 to:
- Browse multiple scan results
- Filter and sort projects by complexity, bucket, CI status, etc.
- View detailed migration estimates and recommendations

## Output

The discovery agent produces two files in the output directory:

### `inventory.json`

A comprehensive JSON file containing:

```json
{
  "run": {
    "started_at": "2024-01-15T10:00:00+00:00",
    "finished_at": "2024-01-15T10:15:00+00:00",
    "base_url": "https://gitlab.com",
    "root_group": "my-organization",
    "stats": {
      "groups": 5,
      "projects": 42,
      "errors": 2,
      "api_calls": 350
    }
  },
  "groups": [
    {
      "id": 12345,
      "full_path": "my-organization",
      "projects": [1, 2, 3]
    }
  ],
  "projects": [
    {
      "id": 1,
      "path_with_namespace": "my-organization/my-project",
      "default_branch": "main",
      "archived": false,
      "visibility": "private",
      "facts": {
        "has_ci": true,
        "has_lfs": false,
        "mr_counts": {"open": 5, "merged": 100, "closed": 10, "total": 115},
        "issue_counts": {"open": 20, "closed": 80, "total": 100},
        "repo_profile": {
          "branches_count": 15,
          "tags_count": 42,
          "has_submodules": false,
          "has_lfs": false
        },
        "ci_profile": {
          "present": true,
          "total_lines": 120,
          "features": {"include": true, "services": true, "rules": true},
          "runner_hints": {"uses_tags": true, "docker_in_docker": true}
        },
        "migration_estimate": {
          "work_score": 45,
          "bucket": "M",
          "drivers": ["Has GitLab CI configuration", "Uses includes", "Uses services"]
        }
      },
      "readiness": {
        "complexity": "medium",
        "blockers": ["Has GitLab CI/CD pipeline - requires conversion to GitHub Actions"],
        "notes": ["Consider renaming default branch from 'master' to 'main'"]
      },
      "errors": []
    }
  ]
}
```

### `summary.txt`

A human-readable summary:

```
DISCOVERY SUMMARY
Base URL: https://gitlab.com
Root Group: my-organization
Started: 2024-01-15T10:00:00+00:00
Finished: 2024-01-15T10:15:00+00:00

STATISTICS
  Groups: 5
  Projects: 42
  API Calls: 350
  Errors: 2

PROJECT BREAKDOWN
  Complexity - Low: 20, Medium: 15, High: 7
  With CI/CD: 25
  With LFS: 3
  Archived: 5
  With Blockers: 12

Output: ./out/inventory.json
```

## Schema

The output follows a strict JSON schema. Key fields:

### Project Facts

| Field | Type | Description |
|-------|------|-------------|
| `has_ci` | `boolean \| "unknown"` | Whether `.gitlab-ci.yml` exists |
| `has_lfs` | `boolean \| "unknown"` | Whether Git LFS is used |
| `mr_counts` | `object \| "unknown"` | Merge request counts by state |
| `issue_counts` | `object \| "unknown"` | Issue counts by state |

### Readiness Assessment

| Field | Type | Description |
|-------|------|-------------|
| `complexity` | `"low" \| "medium" \| "high"` | Estimated migration complexity |
| `blockers` | `string[]` | Issues that may block migration |
| `notes` | `string[]` | Additional observations |

### Complexity Factors

- **Low**: Archived projects, no CI, no LFS, minimal activity
- **Medium**: Active projects with CI configuration
- **High**: Projects with LFS, high activity, complex CI pipelines

## Architecture

```
discovery_agent/
├── __init__.py          # Package initialization
├── __main__.py          # CLI entry point
├── config.py            # Configuration management
├── gitlab_client.py     # GitLab REST API client
├── tools.py             # Individual API operations
├── agent_logic.py       # Planning and decision making
├── orchestrator.py      # Main workflow controller
├── schema.py            # JSON schema validation
└── utils.py             # Utility functions
```

### Agent-Based Design

The discovery process uses an "agent" pattern:

1. **Planner**: Decides what action to take based on current state
2. **Executor**: Performs the action and updates state
3. **State**: Tracks discovered groups, projects, and missing facts

This design allows for:
- Graceful handling of errors and partial failures
- Budget-aware execution (API call limits)
- Easy extension for future enhancements

## API Budget

The agent respects two budget limits:

- `--max-api-calls`: Total API calls across all operations (default: 5000)
- `--max-per-project-calls`: Maximum calls for a single project (default: 200)

When a budget is exceeded, the agent stops gracefully and outputs a partial inventory with whatever data was collected.

## Limitations

1. **No Migration**: This tool only discovers and reports; it does not perform migration
2. **No GitHub API**: This tool does not interact with GitHub
3. **Read-Only**: Only GET requests are made; no modifications to GitLab
4. **Token Permissions**: Limited by the permissions of the provided token
5. **Large Counts**: MR/issue counts over 1000 may show as ">1000" in light mode
6. **Empty Repositories**: Projects without commits may have limited discoverable facts

## Error Handling

Errors are captured per-project in the `errors` array:

```json
{
  "errors": [
    {
      "step": "detect_ci",
      "status": 403,
      "message": "Permission denied"
    }
  ]
}
```

Common error scenarios:
- `403`: Token lacks required permissions
- `404`: Resource not found (empty repo, deleted file)
- `429`: Rate limit exceeded (handled with backoff)
- `5xx`: Server errors (retried automatically)

## Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=discovery_agent

# Run specific test file
pytest tests/test_pagination.py -v
```

## Self-Managed GitLab

The agent supports self-managed GitLab instances:

```bash
python -m discovery_agent \
  --base-url https://gitlab.mycompany.com \
  --token glpat-xxx \
  --root-group my-group
```

Ensure:
- The URL is accessible from your machine
- API v4 is enabled on the instance
- Token has the required scopes

## Environment Variables

| Variable | CLI Equivalent | Description |
|----------|---------------|-------------|
| `GITLAB_BASE_URL` | `--base-url` | GitLab instance URL |
| `GITLAB_TOKEN` | `--token` | Personal Access Token |
| `GITLAB_ROOT_GROUP` | `--root-group` | Root group to scan |
| `OUTPUT_DIR` | `--out` | Output directory |
| `MAX_API_CALLS` | `--max-api-calls` | API call budget |
| `MAX_PER_PROJECT_CALLS` | `--max-per-project-calls` | Per-project budget |

CLI arguments take precedence over environment variables.

## License

MIT License - see LICENSE file for details.
