# Action Reversibility Reference

Quick reference for which migration actions can be rolled back.

## Legend

- ✅ **Fully Reversible** - Action can be completely undone
- ⚠️ **Partially Reversible** - Action can be partially undone (e.g., closed but not deleted)
- ❌ **Non-Reversible** - Action cannot be undone

## Repository Actions

| Action | Status | Rollback Behavior | Notes |
|--------|--------|-------------------|-------|
| `repo_create` | ✅ | Deletes repository | Complete removal including all contents |
| `repo_push` | ❌ | Cannot undo | Git history is immutable once pushed |
| `lfs_configure` | ❌ | Not implemented | LFS objects persist |
| `repo_configure` | ✅ | No rollback needed | Configuration changes don't require cleanup |

## Issue & PR Actions

| Action | Status | Rollback Behavior | Notes |
|--------|--------|-------------------|-------|
| `label_create` | ✅ | Deletes label | Complete removal |
| `milestone_create` | ✅ | Deletes milestone | Complete removal |
| `issue_create` | ⚠️ | Closes issue | GitHub API doesn't support deletion. Issue is closed with rollback comment |
| `issue_comment_add` | ❌ | Cannot undo | GitHub API doesn't support comment deletion |
| `pr_create` | ⚠️ | Closes PR | GitHub API doesn't support deletion. PR is closed with rollback comment |
| `pr_comment_add` | ❌ | Cannot undo | GitHub API doesn't support comment deletion |

## Release Actions

| Action | Status | Rollback Behavior | Notes |
|--------|--------|-------------------|-------|
| `release_create` | ✅ | Deletes release | Complete removal including assets |
| `release_asset_upload` | ✅ | Included in release deletion | Assets deleted with parent release |

## CI/CD Actions

| Action | Status | Rollback Behavior | Notes |
|--------|--------|-------------------|-------|
| `workflow_commit` | ❌ | Cannot undo | Workflow files are in git history |
| `environment_create` | ✅ | Not yet implemented | Would delete environment |
| `secret_set` | ✅ | Not yet implemented | Would delete secret |
| `variable_set` | ✅ | Not yet implemented | Would delete variable |

## Settings Actions

| Action | Status | Rollback Behavior | Notes |
|--------|--------|-------------------|-------|
| `protection_set` | ✅ | Removes branch protection | Restores to unprotected state |
| `collaborator_add` | ✅ | Removes collaborator | Complete removal |
| `webhook_create` | ✅ | Deletes webhook | Complete removal |

## Wiki & Package Actions

| Action | Status | Rollback Behavior | Notes |
|--------|--------|-------------------|-------|
| `wiki_push` | ❌ | Cannot undo | Wiki content is in git history |
| `package_publish` | ❌ | Cannot undo | Published packages cannot be unpublished |

## Preservation Actions

| Action | Status | Rollback Behavior | Notes |
|--------|--------|-------------------|-------|
| `artifact_commit` | ❌ | Cannot undo | Files are in git history |

## Summary Statistics

- **Total Actions**: 24
- **Fully Reversible**: 8 (33%)
- **Partially Reversible**: 2 (8%)
- **Non-Reversible**: 14 (59%)

## Implementation Priority

Actions marked as "Not yet implemented" for rollback:

1. `environment_create` - Medium priority
2. `secret_set` - Medium priority
3. `variable_set` - Medium priority

These actions have GitHub API support for deletion but rollback is not yet implemented.

## Common Patterns

### Fully Reversible Pattern

Actions that create standalone resources via API:
- Create repository → Delete repository
- Create label → Delete label
- Create webhook → Delete webhook

### Partially Reversible Pattern

Actions that create resources the API can't delete:
- Create issue → Close issue (can't delete via API)
- Create PR → Close PR (can't delete via API)

### Non-Reversible Pattern

Actions that involve git history or immutable operations:
- Push code → Cannot remove from git history
- Commit workflow → File is in git history
- Add comment → API doesn't support deletion
- Publish package → Packages can't be unpublished

## Best Practices

1. **Always test rollback** - Before running production migrations, test rollback on a sample repository
2. **Document non-reversible actions** - Make users aware which actions cannot be undone
3. **Manual cleanup checklist** - Provide a checklist for manual cleanup of non-reversible actions
4. **Consider timing** - Roll back as soon as possible after failure to minimize manual intervention needed

## Extending Rollback Support

To add rollback support for a new action:

```python
# 1. Add rollback_data to execute() return
return ActionResult(
    success=True,
    action_id=self.action_id,
    action_type=self.action_type,
    outputs={"resource_id": resource.id},
    rollback_data={
        "target_repo": target_repo,
        "resource_id": resource.id
    }
)

# 2. Implement rollback() method
async def rollback(self, rollback_data: Dict[str, Any]) -> bool:
    try:
        # Get resource and delete it
        resource_id = rollback_data.get("resource_id")
        resource = self.get_resource(resource_id)
        resource.delete()
        return True
    except Exception as e:
        self.logger.error(f"Rollback failed: {e}")
        return False

# 3. Mark as reversible (or not)
def is_reversible(self) -> bool:
    return True  # or False
```

## Related Documentation

- [ROLLBACK.md](./ROLLBACK.md) - Complete rollback documentation
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture
- [API Documentation](./API.md) - API reference
