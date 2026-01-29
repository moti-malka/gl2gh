# User Mapping & Identity Resolution Specification

## Overview
User mapping is critical for preserving authorship, assignments, and mentions across GitLab → GitHub migration. This document specifies how to safely and accurately map GitLab users to GitHub users.

## Problem Statement
GitLab and GitHub use different identity systems:
- **GitLab**: Users have `id`, `username`, `email`, `name`
- **GitHub**: Users have `login`, `email` (if public), `name`

We need to map:
- Issue authors
- Issue assignees
- Issue commenters
- MR authors
- MR reviewers
- MR commenters
- Commit authors (Git email)
- Project members
- Approval rules
- CODEOWNERS

## Mapping Strategy

### 1. Automatic Mapping (Phase 1)

#### Email-based Matching
- Match GitLab user email → GitHub user email
- **Limitation**: GitHub emails may be private
- **Confidence**: High when match found

```python
def match_by_email(gitlab_user, github_users):
    gitlab_email = gitlab_user['email'].lower()
    for gh_user in github_users:
        if gh_user['email'] and gh_user['email'].lower() == gitlab_email:
            return gh_user
    return None
```

#### Username-based Matching
- Match GitLab username → GitHub login (if identical)
- **Confidence**: Medium (usernames may differ)

```python
def match_by_username(gitlab_user, github_users):
    gitlab_username = gitlab_user['username'].lower()
    for gh_user in github_users:
        if gh_user['login'].lower() == gitlab_username:
            return gh_user
    return None
```

#### Organization Membership Cross-reference
- If both are in same org/group, higher confidence
- Match by comparing member lists

```python
def match_by_org_membership(gitlab_user, gitlab_group, github_users, github_org):
    # If user is member of both, likely same person
    # Compare display names, commit history, etc.
    pass
```

### 2. Manual Mapping (Phase 2)

User reviews automatic mappings and:
- **Confirms** correct matches
- **Overrides** incorrect matches
- **Maps** unmapped users
- **Handles** edge cases

### 3. Fallback Strategy (Phase 3)

For unmapped users:
- **Option A**: Use @ghost (GitHub's deleted user placeholder)
- **Option B**: Attribute in text: "Originally by @username on GitLab"
- **Option C**: Create placeholder account (requires GitHub seats)
- **Option D**: Map to a generic "migration-bot" account

## Data Model

### User Mapping Table

```json
{
  "mapping_version": "1.0",
  "created_at": "2024-01-15T10:00:00Z",
  "mappings": [
    {
      "gitlab": {
        "id": 12345,
        "username": "johndoe",
        "email": "john@example.com",
        "name": "John Doe"
      },
      "github": {
        "login": "johndoe",
        "email": "john@example.com",
        "name": "John Doe"
      },
      "confidence": "high",
      "method": "email",
      "confirmed_by_user": true
    },
    {
      "gitlab": {
        "id": 67890,
        "username": "jane-smith",
        "email": "jane@example.com",
        "name": "Jane Smith"
      },
      "github": {
        "login": "jsmith",
        "email": "jane@example.com",
        "name": "Jane Smith"
      },
      "confidence": "medium",
      "method": "manual",
      "confirmed_by_user": true
    },
    {
      "gitlab": {
        "id": 11111,
        "username": "olduser",
        "email": "old@example.com",
        "name": "Old User"
      },
      "github": null,
      "confidence": "none",
      "method": "unmapped",
      "fallback_strategy": "text_attribution",
      "confirmed_by_user": true
    }
  ]
}
```

### MongoDB Schema

```python
class UserMapping(MongoBaseModel):
    """User mapping for GitLab → GitHub"""
    project_id: PyObjectId
    gitlab_user_id: int
    gitlab_username: str
    gitlab_email: str
    gitlab_name: str
    
    github_login: Optional[str] = None
    github_id: Optional[int] = None
    
    confidence: str  # "high", "medium", "low", "none"
    method: str  # "email", "username", "manual", "unmapped"
    fallback_strategy: Optional[str] = None  # "ghost", "text_attribution", "placeholder", "bot"
    
    confirmed_by_user: bool = False
    confirmed_at: Optional[datetime] = None
    confirmed_by: Optional[PyObjectId] = None  # User who confirmed
    
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

## Agent Responsibilities

### Discovery Agent
**Output**: List of unique GitLab users involved in project
```json
{
  "users": [
    {
      "id": 12345,
      "username": "johndoe",
      "email": "john@example.com",
      "name": "John Doe",
      "roles": ["author", "assignee", "commenter", "member"],
      "activity_count": 150
    }
  ]
}
```

### Transform Agent
**Input**: GitLab users list + GitHub org members
**Output**: `user_mapping.json` with automatic matches
**Process**:
1. Fetch GitHub org members
2. Attempt email matching
3. Attempt username matching
4. Attempt org cross-reference
5. Mark confidence levels
6. Identify unmapped users
7. Generate UI prompts for manual review

### Apply Agent
**Input**: Confirmed user mappings
**Action**: Use mappings when creating issues/PRs/comments
**Fallback**: Apply fallback strategy for unmapped users

## UI Requirements

### User Mapping Page

#### Section 1: Automatic Matches (High Confidence)
```
✓ Confirmed Automatically (15 users)
  
  [✓] johndoe → johndoe (matched by email)
  [✓] janesmith → janesmith (matched by email)
  [✓] bobwilson → bobwilson (matched by username)
  ...
  
  [Review All] [Accept All]
```

#### Section 2: Suggested Matches (Medium Confidence)
```
⚠ Needs Review (5 users)
  
  [ ] alice-jones → alicej (matched by similar username)
      GitLab: alice-jones (alice@example.com)
      GitHub: alicej (alice.jones@example.com)
      [Accept] [Change] [Skip]
  
  [ ] old-username → new-username (org member)
      GitLab: old-username (user@example.com)
      GitHub: new-username (user@example.com)
      [Accept] [Change] [Skip]
  ...
  
  [Review All]
```

#### Section 3: Manual Mapping Required
```
✗ Unmapped (3 users)
  
  [ ] contractor123 (no match found)
      GitLab: contractor123 (contractor@external.com)
      
      Map to GitHub user:
      [Search GitHub user...] [Auto-complete dropdown]
      
      Or use fallback:
      ( ) @ghost (deleted user placeholder)
      ( ) Text attribution "Originally by @contractor123"
      (•) Map to @migration-bot
      
      [Save Mapping]
  
  ...
```

#### Section 4: Statistics
```
Summary:
  Total GitLab users: 23
  Mapped (high confidence): 15
  Mapped (needs review): 5
  Unmapped: 3
  
  Migration impact:
    - Issues: 45 will be created with correct authors
    - PRs: 12 will be created with correct authors
    - Comments: 234 will be attributed correctly
  
[Continue to Secrets Setup]
```

## API Endpoints

### Get User Mappings
```
GET /api/projects/{project_id}/user-mappings
```

Response:
```json
{
  "total": 23,
  "mapped": 20,
  "unmapped": 3,
  "mappings": [...]
}
```

### Confirm User Mapping
```
POST /api/projects/{project_id}/user-mappings/{mapping_id}/confirm
```

Body:
```json
{
  "github_login": "johndoe",
  "override": false
}
```

### Batch Confirm
```
POST /api/projects/{project_id}/user-mappings/confirm-all
```

Body:
```json
{
  "mapping_ids": [1, 2, 3],
  "confidence_threshold": "high"
}
```

### Set Fallback Strategy
```
PATCH /api/projects/{project_id}/user-mappings/{mapping_id}/fallback
```

Body:
```json
{
  "fallback_strategy": "text_attribution"
}
```

## Text Attribution Format

When using text attribution fallback:

### Issue
```markdown
# Original Issue Title

_Originally created by @original-username on GitLab on 2024-01-15_

Original description...
```

### Comment
```markdown
_Originally posted by @original-username on 2024-01-15 10:30:00_

Original comment text...
```

### PR
```markdown
# Original PR Title

_Originally created by @original-username on GitLab on 2024-01-15_
_Original reviewers: @reviewer1, @reviewer2_

Original description...
```

## Security Considerations

### Email Privacy
- Never expose user emails in UI without permission
- Only show "matched by email" without showing the email
- Respect GitHub's email privacy settings

### Permissions
- Only project members can configure mappings
- Audit log all mapping changes
- Prevent mapping to users outside GitHub org (without warning)

### Data Protection
- Store user mapping in encrypted form
- Allow users to request removal from mapping
- Comply with GDPR/privacy regulations

## Validation Rules

### Before Apply
1. All "required" users must be mapped or have fallback strategy
2. No duplicate mappings (1 GitLab user → 1 GitHub user)
3. GitHub users must exist and be accessible
4. Warn if mapping to users outside org
5. Confirm if using @ghost or bots

### During Apply
1. Verify GitHub user exists before mentioning
2. Handle @mentions in text properly
3. Preserve original username in metadata
4. Track attribution method used

## Testing Strategy

### Unit Tests
- Email matching algorithm
- Username matching algorithm
- Confidence scoring
- Fallback strategies

### Integration Tests
- API endpoints
- Database operations
- UI workflows

### Manual Tests
- Real GitLab → GitHub user mapping scenarios
- Edge cases (deleted users, renamed users)
- Privacy scenarios

## Edge Cases

### 1. Deleted GitLab Users
- **Detection**: User API returns 404
- **Handling**: Automatic fallback to @ghost or text attribution
- **UI**: Show as "User no longer exists"

### 2. Renamed Users
- **Detection**: Username changed but email same
- **Handling**: Match by email (higher priority)
- **UI**: Show both usernames

### 3. Private Email
- **Detection**: GitHub user email not public
- **Handling**: Username matching only
- **UI**: Show "Email not public" warning

### 4. Same Name, Different Person
- **Detection**: Manual review catches it
- **Handling**: User overrides automatic match
- **UI**: Allow manual search and selection

### 5. GitHub User Not in Org
- **Detection**: User search finds user but not in org
- **Handling**: Warn user, require confirmation
- **UI**: Show warning + option to invite

### 6. Bot Accounts
- **Detection**: GitLab username contains "bot" or is service account
- **Handling**: Map to GitHub bot or text attribution
- **UI**: Suggest bot mapping

## Implementation Priority

### Phase 1: Core Mapping (Week 1)
- [x] Data model
- [ ] Automatic email matching
- [ ] Automatic username matching
- [ ] Store mappings in MongoDB
- [ ] Basic API endpoints

### Phase 2: UI (Week 2)
- [ ] User mapping page (React component)
- [ ] Review interface
- [ ] Manual override
- [ ] Fallback strategy selection

### Phase 3: Integration (Week 3)
- [ ] Export Agent: collect users
- [ ] Transform Agent: generate mappings
- [ ] Apply Agent: use mappings
- [ ] Verify Agent: check attribution

### Phase 4: Advanced Features (Week 4)
- [ ] Org membership cross-reference
- [ ] Smart suggestions
- [ ] Bulk operations
- [ ] Import/export mappings
- [ ] Mapping templates (for repeated migrations)

## Example Workflow

```python
# 1. Discovery Agent collects users
users = discovery_agent.get_all_users(project)
# Result: 50 unique GitLab users

# 2. Transform Agent generates mappings
auto_mappings = transform_agent.map_users(users, github_org)
# Result: 40 high-confidence, 7 medium, 3 unmapped

# 3. UI presents to user
ui.show_mapping_page(auto_mappings)

# 4. User reviews and confirms
user.confirm_high_confidence()  # Accept all 40
user.review_medium_confidence()  # Manually review 7
user.set_fallback_for_unmapped()  # Choose strategy for 3

# 5. Mappings stored
db.save_confirmed_mappings(mappings)

# 6. Apply Agent uses mappings
for issue in issues:
    gh_author = get_mapped_user(issue.author_id)
    if gh_author:
        github.create_issue(..., attribution_comment(gh_author))
    else:
        github.create_issue(..., text_attribution(issue.author))
```

## Metrics to Track

- Mapping success rate (% automatically mapped)
- Confidence distribution
- User review time
- Fallback strategy usage
- Attribution accuracy

## Success Criteria

✅ 80%+ users automatically mapped (high confidence)
✅ 100% users reviewed and confirmed
✅ No incorrect attributions in final migration
✅ Clear audit trail of all mappings
✅ User privacy respected throughout process
