# Migration Coverage - Complete Specification

## Overview
This document specifies the **complete** migration coverage for all GitLab components to GitHub. Nothing is marked as "optional" or "future" - everything listed here must be migrated.

## Migration Strategy
For each component, we use one of these patterns:
- **Direct mapping**: Native equivalent exists in GitHub
- **Best-effort mapping**: Closest equivalent with documented gaps
- **Preserve as artifact**: Export to `migration/` folder + link in PR/Issue
- **Import as commentary**: Preserve as comments/documentation when exact mapping isn't possible

**Result**: Nothing is lost, even if some items can't be represented identically.

---

## 1. Repository & Git Data (CODE) ✅ FULL

### What is Migrated
- Full commit history
- All branches
- All tags
- Submodules (best effort)
- Git LFS pointers + LFS objects (when detected)

### Agent Responsibilities

#### Discovery Agent
- Detect repository size, branch count, tag count
- Detect LFS usage from `.gitattributes`
- Identify submodules
- Report any Git features that may cause issues

#### Export Agent
- Create git bundle: `git bundle create repo.bundle --all`
- Export LFS objects if detected
- Export submodule configuration
- Create `export_manifest.json` with metadata

#### Transform Agent
- N/A (git data is migrated as-is)
- Map default branch name if configured (master → main)

#### Apply Agent
- Create GitHub repository
- Extract and push bundle
- Configure LFS if needed
- Push submodule pointers

#### Verify Agent
- Compare commit count on default branch
- Verify all branches exist
- Verify all tags exist
- Check LFS object count (if LFS used)
- Verify default branch set correctly

---

## 2. CI/CD ✅ FULL (with explicit gaps reporting)

### What is Migrated
- `.gitlab-ci.yml` → `.github/workflows/*.yml`
- Local includes resolution
- Remote includes (best effort)
- Runner tags → GitHub runner labels
- Artifacts → `actions/upload-artifact`
- Cache → `actions/cache`
- Services → service containers or docker steps
- Variables → secrets/vars mapping
- Environments → GitHub Environments
- Manual jobs → workflow_dispatch
- Schedules → workflow schedules
- Protected variables → environment secrets

### Agent Responsibilities

#### Discovery Agent
- Parse `.gitlab-ci.yml`
- Detect CI features: includes, services, rules, needs, triggers, child pipelines
- Identify runner tags
- List variables (names only)
- Detect environments
- Identify schedules

#### Export Agent
- Export `.gitlab-ci.yml`
- Download included files (local and remote best effort)
- Export variables metadata (scoped, protected, masked)
- Export environment definitions
- Export schedule configurations
- Export pipeline history summary (last 100 runs)

#### Transform Agent
- Convert GitLab CI → GitHub Actions workflows
- Map stages → jobs with `needs`
- Map rules → `on` triggers + `if` conditions
- Generate `conversion_gaps.json` for unsupported features
- Create secrets/vars mapping plan
- Generate environment configuration
- Create scheduled workflow triggers

#### Apply Agent
- Commit workflows to `.github/workflows/`
- Create GitHub environments
- Set environment secrets (with placeholders for unknowns)
- Set repository secrets/variables
- Configure workflow permissions

#### Verify Agent
- Validate workflow YAML syntax
- Check all workflows committed
- Verify environments created
- Optional: Trigger workflow dispatch and check status
- Report conversion gaps to user

---

## 3. Merge Requests → Pull Requests ✅ FULL

### What is Migrated
- MR title/description
- Labels
- Assignees (via user mapping)
- Reviewers/approvals
- Comments/discussions (threaded → flattened)
- MR state (open/merged/closed)
- Source/target branches
- Linked issues (best effort)
- Pipeline status (as metadata comment)

### Agent Responsibilities

#### Discovery Agent
- Count MRs by state (open/merged/closed)
- Detect MR complexity (comment count, discussion threads)
- Identify required user mappings

#### Export Agent
- Export all MRs with full details
- Export all comments and discussions
- Export diff metadata
- Export approval history
- Export pipeline status per MR
- Download attachments

#### Transform Agent
- Map GitLab users → GitHub users (via mapping table)
- Map labels and milestones
- Plan PR creation strategy
- Generate comment import plan
- Preserve approval history as initial comment

#### Apply Agent
- Ensure source branches exist in GitHub
- Create PRs via GitHub API
- Import description with metadata footer
- Add labels, milestones, assignees
- Request reviewers
- Import comments in chronological order
- Handle merged MRs (create closed PR or skip based on config)

#### Verify Agent
- Count parity: MR count ↔ PR count by state
- Spot-check random sample (5%) for content parity
- Verify comment counts match
- Report any mapping failures

---

## 4. Issues ✅ FULL

### What is Migrated
- Issue title/description
- Labels
- Assignees
- Milestones
- Comments/notes
- State (open/closed)
- Attachments
- Cross-references (issue → issue, issue → MR)

### Agent Responsibilities

#### Discovery Agent
- Count issues by state
- Identify label usage
- Identify milestone usage

#### Export Agent
- Export all issues with full details
- Export all comments/notes
- Download attachments
- Export cross-reference graph

#### Transform Agent
- Map labels (create if needed)
- Map milestones (create if needed)
- Map users for assignees/commenters
- Build cross-reference mapping

#### Apply Agent
- Create milestones
- Create labels
- Create issues in chronological order
- Import comments
- Set assignees
- Upload attachments to GitHub (if possible) or link to artifacts
- Update cross-references after all issues created

#### Verify Agent
- Count parity: issues by state
- Spot-check sample for content/comment parity
- Verify attachments accessible
- Verify cross-references resolved

---

## 5. Wiki ✅ FULL

### What is Migrated
- All wiki pages
- Wiki page history (optional based on config)
- Attachments
- Page structure/hierarchy

### Agent Responsibilities

#### Discovery Agent
- Detect if wiki enabled
- Count wiki pages

#### Export Agent
- Clone wiki repository (`project.wiki.git`)
- Export as bundle or individual files
- Export attachments

#### Transform Agent
- Decide target: GitHub Wiki vs `/docs/wiki/` in main repo
- Convert GitLab wiki syntax to GitHub wiki syntax (if needed)

#### Apply Agent
- If GitHub Wiki: push to wiki repository
- If docs folder: commit to main repo under `/docs/wiki/`
- Upload attachments

#### Verify Agent
- Verify page count matches
- Spot-check random pages for content parity

---

## 6. Releases & Tags Metadata ✅ FULL

### What is Migrated
- All release definitions
- Release notes/descriptions
- Release assets/links
- Asset files (downloaded and re-uploaded)

### Agent Responsibilities

#### Discovery Agent
- Count releases
- Identify release assets

#### Export Agent
- Export all releases with metadata
- Download release assets (if accessible)
- Export asset URLs

#### Transform Agent
- Map release tag references
- Prepare asset upload plan

#### Apply Agent
- Verify tags exist in GitHub (created in git migration)
- Create GitHub Releases
- Upload assets
- Set release as draft/prerelease if applicable

#### Verify Agent
- Verify release count matches
- Verify all releases have correct tags
- Verify asset count per release
- Spot-check asset downloads

---

## 7. Packages / Registry ✅ FULL

### What is Migrated
- Container Registry → GHCR (GitHub Container Registry)
- NPM packages → GitHub Packages (npm)
- Maven packages → GitHub Packages (maven)
- PyPI packages → GitHub Packages (pypi)
- Generic packages → Release assets or GitHub Packages

### Agent Responsibilities

#### Discovery Agent
- Detect enabled registries
- List packages and versions per registry
- Identify package types

#### Export Agent
- Export package metadata
- Download/export package files (if accessible)
- Export package dependency info

#### Transform Agent
- Map to GitHub Packages/GHCR conventions
- Generate package coordinates
- Plan publishing strategy

#### Apply Agent
- Publish to GHCR (docker push)
- Publish to GitHub Packages (npm/maven/pypi/etc.)
- Or upload as release assets for generic packages

#### Verify Agent
- Verify package count and versions
- Pull/install test (optional smoke test)
- Compare metadata

---

## 8. Git LFS ✅ FULL

### What is Migrated
- LFS configuration (`.gitattributes`)
- All LFS objects
- LFS pointer files

### Agent Responsibilities

#### Discovery Agent
- Detect LFS from `.gitattributes` and API
- Report LFS object count and total size

#### Export Agent
- Fetch all LFS objects
- Export LFS configuration

#### Apply Agent
- Configure repository for LFS
- Push LFS objects to GitHub LFS

#### Verify Agent
- Verify LFS enabled
- Compare LFS object count
- Verify pointer files correct
- Sample download LFS files

---

## 9. Project Settings & Governance ✅ FULL

### What is Migrated

#### Branch Protections
- Protected branches → GitHub branch protection rules
- Required approvals → required reviews
- Push restrictions → push allowances
- Status checks → required status checks

#### Members & Permissions
- Project members → collaborators
- Group members → team memberships
- Access levels → GitHub roles (read/write/admin)

#### Merge Request Rules
- Approval rules → CODEOWNERS + branch protections
- Required approvals → required reviewers

#### Repository Settings
- Visibility (public/private/internal)
- Merge method preferences
- Squash options
- Delete source branch settings

### Agent Responsibilities

#### Discovery Agent
- List all protected branches and rules
- List all members with roles
- Export repository settings
- Export approval rules

#### Export Agent
- Export complete settings JSON
- Export member list with roles
- Export protection rules

#### Transform Agent
- Map GitLab roles → GitHub roles
- Map protection rules → GitHub branch protection
- Generate CODEOWNERS if approval rules exist
- Map team structure

#### Apply Agent
- Set repository settings
- Add collaborators or teams
- Create branch protection rules
- Commit CODEOWNERS if generated

#### Verify Agent
- Verify settings applied
- Verify branch protections active
- Verify user access levels

---

## 10. Variables / Secrets / CI Settings ✅ FULL

### What is Migrated
- CI/CD variables (masked/protected/environment-scoped)
- → GitHub Secrets (for sensitive values)
- → GitHub Variables (for non-sensitive values)
- Environment-scoped → Environment secrets
- Group variables → Organization secrets (optional)

### Agent Responsibilities

#### Discovery Agent
- Enumerate variable names, scopes, flags
- Identify which are retrievable vs masked

#### Export Agent
- Export variable metadata (name, scope, protected, masked)
- Export values IF accessible (depends on permissions)
- Flag which need manual input

#### Transform Agent
- Map to GitHub secrets vs variables
- Map environment scoping
- Generate UI prompts for missing values

#### Apply Agent
- Create environments if not exist
- Set repository secrets/variables
- Set environment secrets
- (Optional) set organization secrets

#### Verify Agent
- Verify secret/variable presence (not values)
- Verify environment scoping
- Generate list of secrets user needs to verify manually

---

## 11. Webhooks & Integrations ✅ FULL

### What is Migrated
- Webhook URLs and triggers
- GitLab events → GitHub events mapping
- Integration settings (preserved as documentation)

### Agent Responsibilities

#### Discovery Agent
- List all webhooks
- Identify event types

#### Export Agent
- Export webhook configurations
- Redact sensitive tokens (preserve pattern only)

#### Transform Agent
- Map GitLab events → GitHub events
- Prepare webhook creation plan

#### Apply Agent
- Create webhooks in GitHub
- Configure event types
- Set secret tokens (requires user input)

#### Verify Agent
- Verify webhook presence
- Verify event mappings
- Test webhook delivery (optional)

---

## 12. CI Schedules / Cron ✅ FULL

### What is Migrated
- Pipeline schedules → workflow scheduled triggers
- Cron expressions
- Variable overrides → workflow inputs

### Agent Responsibilities

#### Discovery Agent
- List all pipeline schedules
- Export cron expressions

#### Export Agent
- Export schedule configurations
- Export variable overrides per schedule

#### Transform Agent
- Convert to GitHub Actions schedule syntax
- Map variable overrides to workflow inputs

#### Apply Agent
- Generate/update workflows with schedule triggers

#### Verify Agent
- Verify schedules in workflow files
- Parse cron expressions for correctness

---

## 13. Artifacts, Logs, Pipeline History ✅ FULL "Preservation"

### What is Migrated
- Pipeline definitions
- Recent pipeline run metadata (last 100)
- Artifacts (downloaded if accessible)
- Log snapshots (optional)
- → Preserved in `migration/pipelines/` folder

### Agent Responsibilities

#### Discovery Agent
- Count recent pipelines
- Identify available artifacts

#### Export Agent
- Export pipeline history summary
- Download artifacts (if accessible and not expired)
- Export logs (if accessible)

#### Transform Agent
- Generate preservation structure
- Create index/README for artifacts

#### Apply Agent
- Commit artifacts to `migration/pipelines/` in repo
- OR upload as GitHub Release assets
- Create index PR/Issue explaining preservation

#### Verify Agent
- Verify artifacts committed
- Verify index accessible

---

## 14. Boards, Epics, Roadmaps ✅ FULL

### What is Migrated
- Issue boards → GitHub Projects (v2)
- Board lists and cards
- Epics → GitHub Issues with epic label + description links
- Roadmaps → Preserved as Markdown + optional Projects

### Agent Responsibilities

#### Discovery Agent
- Detect if boards/epics exist (GitLab tier dependent)
- Count boards and epics

#### Export Agent
- Export board configurations
- Export epic hierarchy
- Export roadmap data

#### Transform Agent
- Map boards → GitHub Projects structure
- Map epics → mega issues with links
- Generate roadmap Markdown

#### Apply Agent
- Create GitHub Projects (v2)
- Add issues to projects
- Create epic issues
- Commit roadmap to repo

#### Verify Agent
- Verify projects created
- Spot-check project items
- Verify epic issues exist

---

## 15. User Mapping & Identity Resolution

### Required Mapping
- GitLab username/email → GitHub username
- GitLab user ID → GitHub user ID

### Sources
1. **Automatic mapping**:
   - Match by email (if public)
   - Match by username (if identical)
   - Org membership lists

2. **Manual mapping**:
   - UI provides mapping table
   - User confirms/overrides mappings
   - Unmapped users → placeholder (@ghost or comment attribution)

### Storage
- `user_mapping.json` in artifacts
- Also in MongoDB for UI display

---

## Component Migration Order (Safe Sequencing)

1. **Phase 1: Repository Foundation**
   - Code + Git data
   - LFS
   - Wiki

2. **Phase 2: CI/CD**
   - Workflows
   - Environments
   - Schedules
   - Variables/Secrets (placeholders)

3. **Phase 3: Issue Tracking**
   - Labels and Milestones
   - Issues
   - Boards
   - Epics

4. **Phase 4: Code Review**
   - Merge Requests → Pull Requests

5. **Phase 5: Releases & Packages**
   - Releases
   - Packages/Registry

6. **Phase 6: Governance**
   - Settings
   - Branch Protections
   - Members/Permissions
   - Webhooks

7. **Phase 7: Preservation**
   - Pipeline history artifacts
   - Anything non-mappable

---

## Verify: Definition of "Done"

A project is fully migrated when ALL of these pass:

✅ Repository
- Repo exists
- Commit count matches (default branch)
- All branches exist
- All tags exist
- LFS configured and objects present (if applicable)

✅ CI/CD
- Workflows exist and parse
- Environments created
- Secrets/variables present (not values)
- Schedules in workflows

✅ Issues
- Count parity (by state)
- Sample content parity
- Comments preserved
- Labels/milestones applied

✅ Pull Requests
- Count parity (by state)
- Sample content parity
- Discussions preserved
- Reviews/approvals noted

✅ Wiki
- Pages present
- Count matches
- Sample content parity

✅ Releases
- Release count matches
- Assets uploaded
- Tag associations correct

✅ Packages
- Package versions present (if applicable)

✅ Settings
- Branch protections active
- Members/teams configured
- Settings applied

✅ Webhooks
- Webhooks created (if enabled)

✅ Preservation
- Artifacts committed
- Pipeline history indexed

---

## UI Requirements for "Everything"

### 1. Connection Setup
- GitLab PAT with required scopes check
- GitHub PAT with required scopes check
- Test connections before proceeding

### 2. User Mapping Interface
- Display detected GitLab users
- Show automatic matches
- Allow manual override
- Handle unmapped users strategy

### 3. Secrets Entry
- List variables that couldn't be exported
- Secure input form for values
- Mark as "optional" or "required"

### 4. Component Selection (Optional Safety)
Even with "everything" scope, allow:
- Disable webhook creation (safety)
- Disable package publishing (safety)
- Disable certain permissions changes (safety)

### 5. Progress Display
- Overall run progress
- Per-project progress with components:
  - Code
  - CI
  - Issues
  - Pull Requests
  - Wiki
  - Releases
  - Packages
  - Settings
  - Webhooks
  - Preservation
  - Verification

### 6. Dry Run vs Apply
- Default: PLAN_ONLY
- Show full plan before apply
- Explicit APPLY confirmation required
- Component-by-component apply (advanced)

---

## Artifacts Structure (Complete)

```
artifacts/runs/<runId>/
  discovery/
    inventory.json
    coverage.json          # NEW: what components exist per project
    readiness.json
    summary.txt
  
  export/<namespace>/<project>/
    repo.bundle
    wiki.bundle           # NEW
    issues.json           # NEW
    mrs.json              # NEW
    releases.json         # NEW
    packages.json         # NEW
    settings.json         # NEW
    webhooks.json         # NEW
    schedules.json        # NEW
    pipelines.json        # NEW
    variables.json        # NEW (metadata only)
    attachments/          # NEW
    artifacts/            # NEW (pipeline artifacts)
    
  transform/<namespace>/<project>/
    workflows/
      *.yml
    mapping_users.json    # NEW
    mapping_labels.json   # NEW
    mapping_milestones.json # NEW
    conversion_gaps.json
    apply_actions.json    # NEW: atomic action list
    
  plan/
    plan.json             # Complete plan with all components
    plan.md
    ui_prompts.json       # NEW: missing inputs needed from user
    
  apply/
    apply_report.json     # Per-component success/failure
    apply_audit_log.json  # Append-only audit trail
    
  verify/
    verify_report.json    # Per-component verification
    verify_summary.md
```

---

## Summary

This specification defines **complete migration** of all GitLab components to GitHub with:
- No "optional" or "future" items
- Full Export → Transform → Apply → Verify chain
- Preservation artifacts for non-mappable items
- Component-level progress tracking
- Safe execution with PLAN_ONLY default
- User mapping and secrets management
- Comprehensive verification

Every agent knows exactly what to export, transform, apply, and verify for each component.
