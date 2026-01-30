# Migration Summary Report Feature

## Overview

The migration summary report feature provides a comprehensive view of migration runs, including statistics, manual actions required, and detailed information about migrated components.

## API Endpoint

```
GET /api/runs/{run_id}/report?format={format}
```

### Parameters

- `run_id` (path): The ID of the migration run
- `format` (query): Output format - `json` (default), `markdown`, or `html`

### Authentication

Requires operator-level authentication.

## Response Formats

### JSON Format

Returns a structured JSON object with the following structure:

```json
{
  "run_id": "string",
  "project": {
    "name": "string",
    "id": "string"
  },
  "status": "COMPLETED|FAILED|RUNNING",
  "mode": "FULL|PLAN_ONLY|...",
  "started_at": "ISO8601 timestamp",
  "finished_at": "ISO8601 timestamp",
  "duration_seconds": 123.45,
  "summary": {
    "projects": {
      "total": 0,
      "completed": 0,
      "failed": 0
    },
    "components": {
      "issues": {
        "migrated": 0,
        "skipped": 0,
        "failed": 0
      },
      "merge_requests_to_prs": {
        "migrated": 0,
        "skipped": 0,
        "failed": 0
      },
      "pipelines_to_actions": {
        "migrated": 0,
        "skipped": 0,
        "failed": 0
      },
      "releases": {
        "migrated": 0,
        "skipped": 0,
        "failed": 0
      }
    }
  },
  "manual_actions": [
    {
      "type": "ci_secrets|webhooks|verification_issue",
      "priority": "high|medium|low",
      "description": "string",
      "project": "string"
    }
  ],
  "migration_details": {
    "projects": [
      {
        "gitlab_project_id": 0,
        "path": "string",
        "status": {},
        "errors": []
      }
    ],
    "artifacts": [
      {
        "type": "string",
        "count": 0
      }
    ]
  },
  "error": null,
  "generated_at": "ISO8601 timestamp"
}
```

### Markdown Format

Returns a formatted Markdown document with:
- Project name and status
- Duration information
- Summary table with component statistics
- Manual actions required section
- Project list with status indicators

Example:
```markdown
# Migration Report
**Project:** myproject
**Status:** ✅ COMPLETED

## Summary
| Component | Migrated | Skipped | Failed |
|-----------|----------|---------|--------|
| Issues | 156 | 3 | 0 |
| Merge Requests → PRs | 89 | 5 | 1 |

## Manual Actions Required ⚠️
1. **5 CI/CD Secrets** need to be copied manually
2. **2 Webhooks** need URL updates
```

### HTML Format

Returns a styled HTML document with:
- Embedded CSS styling
- Structured tables
- Color-coded status indicators
- Highlighted manual actions section

## Usage Examples

### Get JSON Report

```bash
curl -X GET "https://api.example.com/api/runs/507f1f77bcf86cd799439011/report" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Get Markdown Report

```bash
curl -X GET "https://api.example.com/api/runs/507f1f77bcf86cd799439011/report?format=markdown" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Get HTML Report

```bash
curl -X GET "https://api.example.com/api/runs/507f1f77bcf86cd799439011/report?format=html" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Implementation Details

### Service Layer

The `MigrationReportGenerator` service in `app/services/report_service.py` handles:
- Data aggregation from multiple sources (runs, run_projects, artifacts)
- Statistics calculation from apply_report artifacts
- Manual action identification from project readiness and verification reports
- Format conversion (JSON, Markdown, HTML)

### Data Sources

The report aggregates data from:
1. **MigrationRun** collection: Overall run status, timestamps, mode
2. **RunProject** collection: Individual project status, errors
3. **Artifacts** collection: Apply reports, verification reports
4. **MigrationProject** collection: Project metadata

### Manual Action Detection

The service identifies manual actions by:
- Checking `readiness.has_ci_variables` for CI/CD secrets
- Checking `facts.webhook_count` for webhooks
- Parsing verification reports for discrepancies

## Error Handling

The endpoint returns appropriate HTTP status codes:
- `200 OK`: Report generated successfully
- `400 Bad Request`: Invalid format parameter
- `404 Not Found`: Run not found
- `500 Internal Server Error`: Report generation failed

## Testing

Unit tests are available in `backend/tests/test_report_service.py` covering:
- JSON format generation
- Markdown format generation
- HTML format generation
- Manual action identification
- Error handling for invalid inputs
