# Verify Agent - Usage Guide

## Overview

The Verify Agent validates that a GitLab to GitHub migration was successful by comparing the expected state with the actual state of the migrated repository on GitHub.

## Features

### Comprehensive Verification

The Verify Agent checks 9 major components:

1. **Repository** - Branches, tags, commits, LFS configuration
2. **CI/CD** - Workflows, environments, secrets, variables
3. **Issues** - Count, states, labels, milestones
4. **Pull Requests** - Count, states, review comments
5. **Wiki** - Enabled status, page count
6. **Releases** - Count, tags, assets
7. **Packages** - Count, versions (when applicable)
8. **Settings** - Branch protection, collaborators, webhooks
9. **Preservation** - Migration artifacts in `.github/migration/`

### Output Artifacts

The agent generates 4 comprehensive reports:

1. **verify_report.json** - Structured verification results with all details
2. **verify_summary.md** - Human-readable summary with status emojis
3. **component_status.json** - Quick status overview per component
4. **discrepancies.json** - Detailed list of all discrepancies found

## Usage

### Basic Usage

```python
from app.agents.verify_agent import VerifyAgent

# Initialize the agent
agent = VerifyAgent()

# Prepare inputs
inputs = {
    "github_token": "ghp_your_github_token",
    "github_repo": "owner/repo",
    "expected_state": {
        "repository": {
            "branch_count": 5,
            "tag_count": 10,
            "lfs_enabled": True
        },
        "ci_cd": {
            "workflow_count": 3,
            "environment_count": 2
        },
        "issues": {
            "issue_count": 50
        },
        "pull_requests": {
            "pr_count": 20
        },
        "wiki": {
            "wiki_enabled": True
        },
        "releases": {
            "release_count": 5
        },
        "packages": {
            "package_count": 0
        },
        "settings": {},
        "preservation": {
            "preservation_expected": True
        }
    },
    "output_dir": "/path/to/output/directory"
}

# Execute verification
result = await agent.execute(inputs)

# Check results
if result["status"] == "success":
    print("✅ Verification passed!")
    print(f"Components verified: {result['outputs']['components_verified']}")
else:
    print(f"⚠️ Verification status: {result['status']}")
    print(f"Errors: {result['outputs']['total_errors']}")
    print(f"Warnings: {result['outputs']['total_warnings']}")
```

### With GitLab Source Comparison

For more accurate verification, you can optionally provide GitLab credentials to fetch source data:

```python
inputs = {
    "github_token": "ghp_your_github_token",
    "github_repo": "owner/repo",
    "gitlab_token": "glpat_your_gitlab_token",  # Optional
    "gitlab_url": "https://gitlab.com/api/v4",   # Optional
    "expected_state": {...},
    "output_dir": "/path/to/output"
}
```

### Building Expected State from Export

If you have export data from the Export Agent:

```python
import json
from pathlib import Path

# Load export data
export_dir = Path("artifacts/run_123/export/namespace/project")

with open(export_dir / "export_manifest.json") as f:
    manifest = json.load(f)

# Build expected state from manifest
expected_state = {
    "repository": {
        "branch_count": manifest["repository"]["branch_count"],
        "tag_count": manifest["repository"]["tag_count"],
        "lfs_enabled": manifest["repository"].get("lfs_enabled", False)
    },
    "ci_cd": {
        "workflow_count": len(manifest.get("workflows", [])),
        "environment_count": len(manifest.get("environments", []))
    },
    "issues": {
        "issue_count": manifest["issues"]["total_count"]
    },
    # ... build other components
}
```

## Expected State Format

### Repository

```json
{
  "branch_count": 5,
  "tag_count": 10,
  "lfs_enabled": true
}
```

### CI/CD

```json
{
  "workflow_count": 3,
  "environment_count": 2
}
```

### Issues

```json
{
  "issue_count": 50
}
```

### Pull Requests

```json
{
  "pr_count": 20
}
```

### Wiki

```json
{
  "wiki_enabled": true
}
```

### Releases

```json
{
  "release_count": 5
}
```

### Packages

```json
{
  "package_count": 0
}
```

### Settings

```json
{
  "protected_branches": 2,
  "collaborators": 5
}
```

### Preservation

```json
{
  "preservation_expected": true
}
```

## Understanding Verification Results

### Status Values

- **success** - All checks passed, no errors or warnings
- **partial** - Some checks passed with warnings but no critical errors
- **failed** - Critical errors found during verification

### Severity Levels

Discrepancies are categorized by severity:

- **error** - Critical issue that indicates migration failure
- **warning** - Non-critical difference that should be reviewed
- **info** - Informational difference (expected or minor)

### Example Report Structure

```json
{
  "verification_timestamp": "2024-01-29T12:00:00Z",
  "overall_status": "SUCCESS",
  "components": {
    "repository": {
      "status": "success",
      "checks": [
        {
          "name": "repository_exists",
          "passed": true,
          "details": {"name": "owner/repo"}
        },
        {
          "name": "branches_migrated",
          "passed": true,
          "details": {"count": 5}
        }
      ],
      "stats": {
        "branch_count": 5,
        "tag_count": 10,
        "default_branch": "main"
      },
      "errors": [],
      "warnings": []
    }
  },
  "summary": {
    "total_components": 9,
    "components_passed": 9,
    "components_with_warnings": 0,
    "components_failed": 0,
    "total_checks": 45,
    "total_discrepancies": 0
  }
}
```

## Best Practices

### 1. Use Tolerances for Large Datasets

For large repositories, exact counts may vary due to timing or filtering. The agent uses a 5% tolerance for counts:

```python
# If you expect 100 issues, the agent will accept 95-105
expected_state = {
    "issues": {
        "issue_count": 100  # Will pass if actual is 95-105
    }
}
```

### 2. Verify Incrementally

Run verification in stages:

1. First verify repository and CI/CD
2. Then verify issues and pull requests
3. Finally verify all other components

### 3. Review Warnings

Not all warnings indicate problems. Review them to determine if they're acceptable:

- Branch count differences might be expected if feature branches were excluded
- Tag differences might occur if lightweight tags weren't migrated
- Issue count differences might be due to spam/bot issues being filtered

### 4. Save Verification Reports

Always save verification reports for audit purposes:

```python
# Reports are automatically saved to output_dir/verify/
# - verify_report.json
# - verify_summary.md
# - component_status.json
# - discrepancies.json
```

## Integration with Migration Pipeline

The Verify Agent should be the last step in the migration pipeline:

```
Discovery → Export → Transform → Plan → Apply → Verify
```

Example orchestration:

```python
async def run_migration_with_verification():
    # ... run other agents ...
    
    # Run Apply Agent
    apply_result = await apply_agent.execute(apply_inputs)
    
    # Build expected state from apply result
    expected_state = build_expected_state_from_apply(apply_result)
    
    # Run Verify Agent
    verify_inputs = {
        "github_token": github_token,
        "github_repo": github_repo,
        "expected_state": expected_state,
        "output_dir": output_dir
    }
    
    verify_result = await verify_agent.execute(verify_inputs)
    
    if verify_result["status"] == "success":
        print("✅ Migration verified successfully!")
    else:
        print("⚠️ Migration verification found issues")
        print(f"Check reports at: {output_dir}/verify/")
```

## Error Handling

The Verify Agent handles errors gracefully:

```python
result = await agent.execute(inputs)

if result["status"] == "failed":
    # Check errors
    for error in result.get("errors", []):
        print(f"Error: {error['message']}")
        if "details" in error:
            print(f"Details: {error['details']}")
    
    # Errors are also in the verify_report.json
    with open(f"{output_dir}/verify/verify_report.json") as f:
        report = json.load(f)
        for component, data in report["components"].items():
            if data["errors"]:
                print(f"\n{component} errors:")
                for error in data["errors"]:
                    print(f"  - {error['message']}")
```

## Troubleshooting

### Rate Limiting

If you encounter rate limiting:

1. The agent uses httpx with 30-second timeouts
2. Add delays between verification runs
3. Use authenticated requests (already done via token)

### Repository Not Accessible

If verification fails with 404:

1. Check that the repository exists
2. Verify token has read permissions
3. Ensure repository visibility matches token scope

### Large Repositories

For very large repositories:

1. Verification may take several minutes
2. The agent samples large datasets (first 5 items)
3. Consider running verification off-peak hours

## Advanced Usage

### Custom Verification Checks

Extend the VerifyAgent for custom checks:

```python
from app.agents.verify_agent import VerifyAgent, VerificationResult

class CustomVerifyAgent(VerifyAgent):
    async def _verify_custom_component(self, repo: str, expected: Dict) -> VerificationResult:
        result = VerificationResult("custom")
        
        # Add your custom verification logic
        
        result.set_status()
        return result
```

### Verification Hooks

Add pre/post verification hooks:

```python
class HookedVerifyAgent(VerifyAgent):
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # Pre-verification hook
        await self.pre_verify_hook(inputs)
        
        # Run verification
        result = await super().execute(inputs)
        
        # Post-verification hook
        await self.post_verify_hook(result)
        
        return result
```

## Performance

Typical verification times:

- Small repository (<100 issues, <10 PRs): 5-10 seconds
- Medium repository (100-1000 issues): 30-60 seconds
- Large repository (>1000 issues): 2-5 minutes

The agent makes approximately:
- 20-30 API calls for basic verification
- Additional calls for sampling (5 items per component)

## Security

The Verify Agent:

- Only performs read operations on GitHub
- Does not modify any repository data
- Stores tokens securely (not logged)
- Masks sensitive data in reports

## Support

For issues or questions:

1. Check the test files for examples
2. Review the MIGRATION_COVERAGE.md documentation
3. Enable debug logging: `logger.setLevel(logging.DEBUG)`
