# Export Agent Documentation

## Overview

The Export Agent is responsible for extracting all data from GitLab projects in preparation for migration to GitHub. It provides comprehensive export functionality for all GitLab components with built-in resumability, progress tracking, and security features.

## Features

### Comprehensive Export Coverage
- **Repository**: Git bundle, LFS detection, submodule configuration
- **CI/CD**: Pipeline configuration, variables, environments, schedules, pipeline history
- **Issues**: Full issues with comments, attachments, and cross-references
- **Merge Requests**: Complete MRs with discussions, approvals, and diff metadata
- **Wiki**: Git bundle export of wiki content
- **Releases**: Release metadata and asset information
- **Packages**: Package registry metadata
- **Settings**: Branch protections, members, webhooks, deploy keys, project settings

### Key Capabilities
- ✅ **Resumable Operations**: Checkpoint system allows resuming from failures
- ✅ **Rate Limiting**: Respects GitLab API rate limits with exponential backoff
- ✅ **Progress Tracking**: Real-time progress events for UI updates
- ✅ **Partial Success**: Continues even if some components fail
- ✅ **Security Conscious**: Masks tokens, secrets, and sensitive data
- ✅ **Error Handling**: Comprehensive error capture and reporting

## Usage

### Basic Export

```python
from app.agents.export_agent import ExportAgent
import asyncio

async def export_project():
    agent = ExportAgent()
    
    inputs = {
        "gitlab_url": "https://gitlab.com",
        "gitlab_token": "your-gitlab-token",
        "project_id": "123",
        "output_dir": "/path/to/export/output"
    }
    
    result = await agent.execute(inputs)
    
    if result["status"] == "success":
        print("Export completed successfully!")
        print(f"Exported to: {result['outputs']['output_dir']}")
    else:
        print(f"Export failed or partial: {result['errors']}")

# Run the export
asyncio.run(export_project())
```

### Resumable Export

If an export fails partway through, you can resume it:

```python
inputs = {
    "gitlab_url": "https://gitlab.com",
    "gitlab_token": "your-gitlab-token",
    "project_id": "123",
    "output_dir": "/path/to/export/output",
    "resume": True  # Enable resume from checkpoint
}

result = await agent.execute(inputs)
```

### Configuration Options

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `gitlab_url` | string | Yes | GitLab instance URL (e.g., https://gitlab.com) |
| `gitlab_token` | string | Yes | Personal Access Token with required scopes |
| `project_id` | int/string | Yes | GitLab project ID |
| `output_dir` | string | Yes | Directory for export output |
| `resume` | boolean | No | Resume from checkpoint (default: False) |
| `max_requests_per_minute` | int | No | API rate limit (default: 300) |

## Output Structure

The export creates the following directory structure:

```
output_dir/
├── .export_checkpoint.json      # Checkpoint file (for resume)
├── export_manifest.json          # Export summary and metadata
├── repository/
│   ├── bundle.git                # Git bundle
│   ├── lfs_detected.txt          # LFS status (if applicable)
│   └── submodules.txt            # Submodule config (if applicable)
├── ci/
│   ├── gitlab-ci.yml             # Main CI config
│   ├── variables.json            # Variable metadata (values masked)
│   ├── environments.json         # Environment definitions
│   ├── schedules.json            # Pipeline schedules
│   └── pipeline_history.json    # Recent pipeline runs
├── issues/
│   └── issues.json               # All issues with comments
├── merge_requests/
│   └── merge_requests.json       # All MRs with discussions
├── wiki/
│   └── wiki.git                  # Wiki bundle (if enabled)
├── releases/
│   └── releases.json             # Release metadata
├── packages/
│   └── packages.json             # Package metadata
└── settings/
    ├── protected_branches.json   # Branch protection rules
    ├── protected_tags.json       # Tag protection rules
    ├── members.json              # Project members and roles
    ├── webhooks.json             # Webhook configs (secrets masked)
    ├── deploy_keys.json          # Deploy keys (masked)
    └── project_settings.json     # General settings
```

## Export Manifest

The `export_manifest.json` file contains metadata about the export:

```json
{
  "project_id": 123,
  "project_path": "namespace/project",
  "exported_at": "2024-01-15T10:30:00Z",
  "gitlab_url": "https://gitlab.com",
  "components": {
    "repository": {
      "status": "completed"
    },
    "ci": {
      "status": "completed",
      "count": 15
    },
    "issues": {
      "status": "completed",
      "count": 42
    },
    ...
  },
  "checkpoint_summary": {
    "total_components": 8,
    "completed": 8,
    "failed": 0,
    "in_progress": 0
  },
  "errors": []
}
```

## Security Considerations

### Token Handling
- Tokens are **never** written to output files
- Error messages are sanitized to remove token strings
- Git operations use authentication URLs that are cleaned from logs

### Secret Masking
The export agent automatically masks sensitive data:
- CI/CD variable **values** (only metadata exported)
- Webhook secret tokens
- Deploy key private data
- Any authentication credentials

### Data Export
The agent exports:
- ✅ Configuration and metadata
- ✅ Code and commits
- ✅ Issues and discussions
- ❌ Variable/secret VALUES (security)
- ❌ Webhook secret tokens (security)

## Error Handling

The export agent uses a multi-level error handling strategy:

1. **Component-Level**: Each component can fail independently
2. **Partial Success**: Export continues even if some components fail
3. **Checkpointing**: Progress is saved for resume capability
4. **Error Collection**: All errors are collected in the manifest

### Status Values
- `success`: All components exported successfully
- `partial`: Some components completed, others failed
- `failed`: Critical failure, no components completed

## Progress Tracking

The agent emits progress events throughout the export process:

```python
# Events are logged via BaseAgent.log_event()
# Example events:
# - "Starting export for project 123"
# - "Exporting repository..."
# - "Exported 10 issues..."
# - "Export completed with status: success"
```

## Checkpointing

The checkpoint system tracks:
- Component completion status
- Last processed item (for issues/MRs)
- Error history
- Progress metrics

Checkpoint file location: `{output_dir}/.export_checkpoint.json`

### Resume Behavior
When `resume=True`:
1. Loads existing checkpoint
2. Skips completed components
3. Resumes in-progress components from last item
4. Continues with pending components

## GitLab API Requirements

### Required Token Scopes
Your GitLab Personal Access Token needs:
- `read_api` - Read API access
- `read_repository` - Read repository data
- `read_registry` - Read package registry (if using packages)

### API Rate Limits
- Default: 300 requests/minute
- Configurable via `max_requests_per_minute`
- Automatic backoff on 429 responses
- Exponential retry on server errors

## Troubleshooting

### Common Issues

**Export hangs during repository clone:**
- Large repositories may take >10 minutes
- Git timeout is set to 10 minutes by default
- Check network connectivity to GitLab

**Issues/MRs export incomplete:**
- Enable resume: `resume=True`
- Check API token permissions
- Review error messages in manifest

**Variables show as empty:**
- This is expected - values are masked for security
- Only metadata (name, scope, flags) is exported

**Wiki export fails:**
- Ensure wiki is enabled in GitLab project
- Check if wiki has any pages
- Verify token has repository read access

### Debug Mode

Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Performance Considerations

### Large Projects
For projects with many issues/MRs:
- Use checkpointing for reliability
- Export may take several hours for thousands of items
- Monitor API rate limits

### Repository Size
- Large repositories (>1GB) may need increased timeouts
- LFS objects require separate handling
- Bundle creation can be memory-intensive

## Integration

The Export Agent integrates with:
- **Event Service**: Progress tracking and logging
- **Artifact Service**: Metadata storage
- **Run Service**: Migration run management
- **Checkpoint System**: Resume capability

## Testing

Run the test suite:
```bash
cd backend
PYTHONPATH=. pytest tests/test_export_agent.py -v
```

All 16 tests should pass.

## Related Documentation

- [MIGRATION_COVERAGE.md](../../docs/MIGRATION_COVERAGE.md) - Complete migration specification
- [GitLab API Client](gitlab_client.md) - API client documentation
- [Checkpoint System](export_checkpoint.md) - Checkpoint system details
