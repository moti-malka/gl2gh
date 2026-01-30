# Branch Protection Rules Migration Guide

## Overview

This document describes how GitLab branch protection rules are transformed and migrated to GitHub branch protection settings during the migration process.

## GitLab to GitHub Protection Mapping

### 1. Access Level Mapping

GitLab uses numeric access levels to control who can perform actions:

| GitLab Access Level | Description | GitHub Equivalent |
|-------------------|-------------|-------------------|
| 0 | No access | Restrictions applied |
| 30 | Developer + Maintainer | Pull request reviews required |
| 40 | Maintainer | Pull request reviews + higher approval count |
| 60 | Admin | Enforce admins setting |

### 2. Push Access Levels

**GitLab:**
```json
{
  "push_access_levels": [
    {"access_level": 40, "user_id": null, "group_id": null}
  ]
}
```

**GitHub Equivalent:**
- When specific users/groups are identified, manual mapping to GitHub users/teams required
- Protection restricts who can push directly to the branch
- **Gap:** GitLab's granular push restrictions require manual user/team configuration in GitHub

### 3. Merge Access Levels

**GitLab:**
```json
{
  "merge_access_levels": [
    {"access_level": 40}
  ],
  "approvals_before_merge": 2
}
```

**GitHub Equivalent:**
```json
{
  "required_pull_request_reviews": {
    "required_approving_review_count": 2,
    "dismiss_stale_reviews": false,
    "require_code_owner_reviews": false
  }
}
```

### 4. Code Owner Approval

**GitLab:**
```json
{
  "code_owner_approval_required": true
}
```

**GitHub Equivalent:**
```json
{
  "required_pull_request_reviews": {
    "require_code_owner_reviews": true
  }
}
```

Additionally generates `.github/CODEOWNERS` file from GitLab approval rules.

### 5. Force Push Settings

**GitLab:**
```json
{
  "allow_force_push": false
}
```

**GitHub Equivalent:**
```json
{
  "allow_force_pushes": false
}
```

✅ **Direct mapping** - Both platforms have equivalent settings.

### 6. Required Status Checks

**GitLab:** Protection rules don't directly configure required CI jobs. Jobs are defined in `.gitlab-ci.yml`.

**GitHub Equivalent:**
```json
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["ci/build", "ci/test", "ci/lint"]
  }
}
```

**Mapping Strategy:** Extract job names from `.gitlab-ci.yml` and configure as required status checks.

### 7. Approval Rules → CODEOWNERS

GitLab approval rules with eligible approvers and file patterns are transformed into a GitHub CODEOWNERS file.

**GitLab Approval Rule:**
```json
{
  "name": "Backend Approval",
  "approvals_required": 2,
  "eligible_approvers": [
    {"id": 123, "username": "alice"},
    {"id": 456, "username": "bob"}
  ],
  "groups": [
    {"path": "backend-team"}
  ],
  "file_pattern": "*.py"
}
```

**Generated CODEOWNERS:**
```
# CODEOWNERS
# Generated from GitLab approval rules

# Rule: Backend Approval
*.py @alice @bob @org/backend-team
```

### 8. Protected Tags

**GitLab:**
```json
{
  "name": "v*",
  "create_access_levels": [{"access_level": 40}]
}
```

**GitHub Equivalent:**
- Tag protection rules (requires GitHub Pro/Enterprise)
- Pattern-based protection

**Gap:** Tag protection requires paid GitHub plan. Free plans can't protect tags.

## Implementation Details

### ProtectionRulesTransformer

The `ProtectionRulesTransformer` class handles all GitLab to GitHub protection rule transformations:

```python
from app.utils.transformers import ProtectionRulesTransformer

transformer = ProtectionRulesTransformer()
result = transformer.transform({
    "protected_branches": gitlab_branches,
    "protected_tags": gitlab_tags,
    "project_members": members,
    "ci_jobs": ["build", "test"],
    "approval_rules": approval_rules
})

# Access transformed data
github_protections = result.data["branch_protections"]
codeowners_content = result.data["codeowners_content"]
gaps = result.data["gaps"]
```

### SetBranchProtectionAction

The enhanced action applies protection settings to GitHub:

```python
action = SetBranchProtectionAction(
    github_client=github_client,
    parameters={
        "target_repo": "owner/repo",
        "branch": "main",
        "required_pull_request_reviews": {
            "required_approving_review_count": 2,
            "require_code_owner_reviews": True,
            "dismiss_stale_reviews": True
        },
        "required_status_checks": {
            "strict": True,
            "contexts": ["ci/build", "ci/test"]
        },
        "allow_force_pushes": False,
        "allow_deletions": False
    }
)
```

### CommitCodeownersAction

Commits the generated CODEOWNERS file to the repository:

```python
action = CommitCodeownersAction(
    github_client=github_client,
    parameters={
        "target_repo": "owner/repo",
        "codeowners_content": codeowners_content,
        "branch": "main"
    }
)
```

## Conversion Gaps

### High Priority Gaps

1. **User/Team Mapping for Push Restrictions**
   - **Issue:** GitLab's push_access_levels with specific user_id or group_id require manual mapping
   - **Action:** Review unmapped users and configure GitHub repository collaborators
   - **Severity:** High

2. **Unprotect Access Level**
   - **Issue:** GitLab's `unprotect_access_level` has no direct GitHub equivalent
   - **Action:** Document who can modify branch protection in GitHub (repository admins)
   - **Severity:** Medium

### Medium Priority Gaps

3. **Tag Protection on Free Plan**
   - **Issue:** GitHub Free doesn't support tag protection rules
   - **Action:** Upgrade to GitHub Pro/Enterprise or manually protect important tags
   - **Severity:** Medium

4. **Approval Rule Complexity**
   - **Issue:** GitLab's complex approval rules (e.g., "any 2 from group X OR 1 from group Y") can't be fully represented in CODEOWNERS
   - **Action:** Simplify to most restrictive rule or configure in GitHub branch protection
   - **Severity:** Medium

### Low Priority Gaps

5. **Default Branch Protection**
   - **Issue:** GitLab allows setting default protection rules for all branches
   - **Action:** Apply protection rules to specific branches individually
   - **Severity:** Low

## Best Practices

### 1. Review Generated CODEOWNERS

Always review the generated CODEOWNERS file before committing:
- Verify user mappings are correct
- Check that file patterns match expected paths
- Ensure team names follow GitHub naming conventions (@org/team-name)

### 2. Test Protection Rules

After migration:
1. Attempt to push directly to protected branch (should fail)
2. Create a pull request and verify approval requirements
3. Test force push restrictions
4. Verify required status checks are enforced

### 3. Document Manual Steps

Some protection features require manual configuration:
- Repository collaborators and their permissions
- Team access levels
- Protected environments
- Deploy keys

### 4. Gradual Rollout

Consider enabling protection rules gradually:
1. Start with main/master branch only
2. Add status checks once CI/CD is validated
3. Enable approval requirements after team onboarding
4. Add CODEOWNERS incrementally by component

## Example: Complete Migration Flow

```python
# 1. Export from GitLab
gitlab_client = GitLabClient(url, token)
protected_branches = await gitlab_client.list_protected_branches(project_id)
approval_rules = await gitlab_client.get_approval_rules(project_id)
ci_config = await gitlab_client.get_file_content(project_id, ".gitlab-ci.yml")

# 2. Transform to GitHub format
transformer = ProtectionRulesTransformer()
ci_transformer = CICDTransformer()

# Extract CI jobs
ci_result = ci_transformer.transform({"gitlab_ci_yaml": ci_config})
ci_jobs = transformer.get_required_status_checks_from_ci(ci_result.data["workflow"])

# Transform protection rules
protection_result = transformer.transform({
    "protected_branches": protected_branches,
    "approval_rules": approval_rules,
    "ci_jobs": ci_jobs,
    "project_members": members
})

# 3. Apply to GitHub
for protection in protection_result.data["branch_protections"]:
    action = SetBranchProtectionAction(github_client, parameters=protection)
    await action.execute()

# 4. Commit CODEOWNERS
if protection_result.data["codeowners_content"]:
    action = CommitCodeownersAction(
        github_client,
        parameters={
            "target_repo": "owner/repo",
            "codeowners_content": protection_result.data["codeowners_content"]
        }
    )
    await action.execute()

# 5. Review gaps
for gap in protection_result.data["gaps"]:
    print(f"{gap['severity']}: {gap['message']}")
```

## Troubleshooting

### Protection Rules Not Applied

**Symptom:** Branch protection settings don't take effect
**Causes:**
1. Insufficient permissions (need admin access)
2. Branch doesn't exist yet
3. Invalid status check names

**Solution:**
1. Verify GitHub token has admin scope
2. Create branches before applying protection
3. Match status check names exactly from CI workflows

### CODEOWNERS Not Working

**Symptom:** Pull requests don't require code owner reviews
**Causes:**
1. File not in correct location (.github/CODEOWNERS)
2. Invalid syntax
3. Users/teams don't have repository access

**Solution:**
1. Verify file path is `.github/CODEOWNERS` (or `CODEOWNERS` in root, or `docs/CODEOWNERS`)
2. Validate syntax: `# comment`, `pattern @owner`
3. Add users/teams as collaborators first

### Status Checks Always Failing

**Symptom:** Required status checks prevent merging
**Causes:**
1. Status check names don't match workflow job names
2. Workflows not yet run on the branch
3. Strict mode requires branch to be up-to-date

**Solution:**
1. Match check names to GitHub Actions job IDs
2. Run workflows at least once
3. Disable strict mode temporarily if needed

## Related Documentation

- [GitHub Branch Protection Rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitHub CODEOWNERS](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)
- [GitLab Protected Branches](https://docs.gitlab.com/ee/user/project/protected_branches.html)
- [GitLab Approval Rules](https://docs.gitlab.com/ee/user/project/merge_requests/approvals/rules.html)

## API References

### GitLab Protected Branch Object

```json
{
  "id": 1,
  "name": "main",
  "push_access_levels": [
    {
      "id": 1,
      "access_level": 40,
      "access_level_description": "Maintainers",
      "user_id": null,
      "group_id": null
    }
  ],
  "merge_access_levels": [
    {
      "id": 1,
      "access_level": 40,
      "access_level_description": "Maintainers",
      "user_id": null,
      "group_id": null
    }
  ],
  "unprotect_access_levels": [
    {
      "id": 1,
      "access_level": 40,
      "access_level_description": "Maintainers",
      "user_id": null,
      "group_id": null
    }
  ],
  "code_owner_approval_required": false,
  "allow_force_push": false
}
```

### GitHub Branch Protection Parameters

```json
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["continuous-integration/jenkins"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "dismissal_restrictions": {
      "users": ["octocat"],
      "teams": ["justice-league"]
    },
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 2
  },
  "restrictions": {
    "users": ["octocat"],
    "teams": ["justice-league"],
    "apps": ["super-ci"]
  },
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": false
}
```
