# Rollback/Undo Feature Documentation

## Overview

The rollback feature allows you to undo migration actions that have been executed on GitHub. This is critical when a migration fails partway through, leaving GitHub repositories in an inconsistent state.

## How It Works

### Action Tracking

During migration execution, the Apply Agent tracks all successful actions that have rollback data:

```python
# Each successful action is tracked
self.executed_actions.append({
    "action_id": "action-001",
    "action_type": "repo_create",
    "action_config": {...},
    "rollback_data": {"repo_full_name": "org/repo", "repo_id": 12345},
    "reversible": True,
    "timestamp": "2024-01-30T12:00:00"
})
```

This information is saved to `executed_actions.json` in the run's artifact directory.

### Rollback Execution

When you trigger a rollback:

1. **Loads executed actions** from `executed_actions.json`
2. **Reverses the order** - actions are undone in reverse execution order
3. **Skips non-reversible actions** - actions marked as non-reversible are logged but skipped
4. **Executes rollback** - calls the `rollback()` method for each action
5. **Saves rollback report** - generates a report of what was rolled back

## API Usage

### Trigger Rollback

```bash
POST /api/runs/{run_id}/rollback
```

**Requirements:**
- Run status must be `FAILED` or `COMPLETED`
- Run must have reached the apply stage (executed_actions.json must exist)
- User must have operator permissions

**Response:**
```json
{
  "message": "Rollback completed",
  "run_id": "abc123",
  "status": "success",
  "rolled_back": 45,
  "skipped": 5,
  "failed": 0,
  "results": [...]
}
```

## Reversible Actions

### ✅ Fully Reversible Actions

These actions can be completely undone:

| Action Type | Rollback Behavior |
|------------|------------------|
| `repo_create` | Deletes the repository |
| `label_create` | Deletes the label |
| `milestone_create` | Deletes the milestone |
| `release_create` | Deletes the release |
| `protection_set` | Removes branch protection |
| `collaborator_add` | Removes the collaborator |
| `webhook_create` | Deletes the webhook |

### ⚠️ Partially Reversible Actions

These actions can be closed/deactivated but not fully deleted:

| Action Type | Rollback Behavior | Limitation |
|------------|------------------|------------|
| `issue_create` | Closes the issue | GitHub API doesn't support deleting issues |
| `pr_create` | Closes the pull request | GitHub API doesn't support deleting PRs |

### ❌ Non-Reversible Actions

These actions **cannot** be undone:

| Action Type | Reason |
|------------|--------|
| `repo_push` | Git history is permanent - once code is pushed, it's in the history |
| `issue_comment_add` | GitHub API doesn't support deleting comments |
| `pr_comment_add` | GitHub API doesn't support deleting comments |

## Action Implementation

### Adding Rollback to a New Action

1. **Add rollback_data to ActionResult:**

```python
return ActionResult(
    success=True,
    action_id=self.action_id,
    action_type=self.action_type,
    outputs={"webhook_id": webhook.id},
    rollback_data={
        "target_repo": target_repo,
        "webhook_id": webhook.id
    }
)
```

2. **Implement the rollback() method:**

```python
async def rollback(self, rollback_data: Dict[str, Any]) -> bool:
    """Rollback webhook creation by deleting it"""
    try:
        target_repo = rollback_data.get("target_repo")
        webhook_id = rollback_data.get("webhook_id")
        
        if not target_repo or not webhook_id:
            self.logger.error("Missing required rollback data")
            return False
        
        repo = self.github_client.get_repo(target_repo)
        hook = repo.get_hook(webhook_id)
        hook.delete()
        
        self.logger.info(f"Successfully rolled back webhook {webhook_id}")
        return True
    except GithubException as e:
        if e.status == 404:
            # Already deleted - consider this success
            return True
        self.logger.error(f"Rollback failed: {str(e)}")
        return False
```

3. **Mark non-reversible actions:**

```python
def is_reversible(self) -> bool:
    """Comments cannot be deleted via GitHub API"""
    return False
```

## Best Practices

### Before Migration

1. **Test on a small project first** - validate rollback works as expected
2. **Have GitHub admin access** - some rollback operations require admin permissions
3. **Backup important data** - rollback may not recover everything

### During Rollback

1. **Review the rollback report** - check what will be rolled back before confirming
2. **Monitor progress** - watch for any failures in the rollback process
3. **Handle manual cleanup** - non-reversible actions require manual cleanup

### After Rollback

1. **Verify GitHub state** - ensure repositories are in the expected state
2. **Check for orphaned resources** - some resources may need manual cleanup
3. **Document issues** - report any problems for future improvements

## Limitations

### API Limitations

GitHub's API has several limitations that affect rollback:

- **Issues and PRs cannot be deleted** - we can only close them
- **Comments cannot be deleted** - they remain in the repository
- **Git history is immutable** - pushed code remains in history
- **Some resources require admin access** - branch protections, webhooks

### Data Loss

Rollback involves **permanent data deletion**. Once rolled back:

- ❌ Repositories are **permanently deleted**
- ❌ Releases and their downloads are **permanently deleted**
- ❌ Webhooks and their delivery history are **permanently deleted**
- ⚠️ Issues and PRs are **closed** (not deleted)

### Timing

- **Rollback should be triggered immediately** - the longer you wait, the more likely manual changes have occurred
- **Concurrent modifications** - if someone modifies resources during rollback, it may fail
- **Rate limits** - rollback consumes GitHub API calls

## Troubleshooting

### "No executed actions found"

**Cause:** The run didn't reach the apply stage, or executed_actions.json wasn't created.

**Solution:** Check run artifacts - you can only rollback runs that have executed actions.

### "Failed to rollback: Repository not found"

**Cause:** Repository was already deleted or you don't have access.

**Solution:** This is expected - rollback considers this success. Check other actions.

### "Rollback partially completed"

**Cause:** Some actions failed to rollback due to permissions or API errors.

**Solution:** 
1. Check rollback report for specific failures
2. Manually clean up failed actions
3. Retry rollback if it was a transient error

### "Cannot rollback run with status RUNNING"

**Cause:** Rollback only works on FAILED or COMPLETED runs.

**Solution:** Wait for the run to finish or cancel it first.

## Examples

### Example 1: Rollback a Failed Migration

```bash
# Migration fails at action #52
# You want to undo actions #1-51

curl -X POST https://api.example.com/api/runs/abc123/rollback \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Result:**
```json
{
  "status": "success",
  "rolled_back": 45,
  "skipped": 6,  // 6 non-reversible actions (code push, comments)
  "failed": 0
}
```

### Example 2: Partial Rollback Due to Permissions

```bash
curl -X POST https://api.example.com/api/runs/def456/rollback \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Result:**
```json
{
  "status": "partial",
  "rolled_back": 40,
  "skipped": 5,
  "failed": 3,  // 3 actions failed - check report for details
  "results": [
    {
      "action_id": "action-030",
      "action_type": "protection_set",
      "status": "failed",
      "reason": "403: Admin access required"
    }
  ]
}
```

## Future Enhancements

Potential improvements for the rollback feature:

1. **Selective rollback** - roll back only specific actions
2. **Dry-run mode** - preview what would be rolled back without executing
3. **Rollback to checkpoint** - roll back to a specific action ID
4. **Improved issue/PR handling** - add clear markers that items were rolled back
5. **Rollback history** - track multiple rollback attempts
6. **Automated cleanup** - better handling of edge cases and orphaned resources

## See Also

- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture and design patterns
- [API Documentation](./API.md) - Complete API reference
- [Migration Guide](./MIGRATION_GUIDE.md) - How to perform migrations
