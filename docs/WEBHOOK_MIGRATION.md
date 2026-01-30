# Webhook Migration: GitLab to GitHub

## Overview

The webhook migration feature automatically transforms GitLab webhook configurations to their GitHub equivalents, handling event type mapping and configuration differences between the two platforms.

## Event Mapping

### Supported Event Mappings

The following GitLab webhook events are automatically mapped to their GitHub equivalents:

| GitLab Event | GitHub Event(s) | Notes |
|--------------|----------------|-------|
| `push_events` | `push` | Direct mapping |
| `tag_push_events` | `create` | GitHub uses 'create' event for tags |
| `issues_events` | `issues` | Direct mapping |
| `confidential_issues_events` | `issues` | GitHub doesn't have confidential issues |
| `merge_requests_events` | `pull_request` | MR → PR mapping |
| `note_events` | `issue_comment`, `pull_request_review_comment` | Comments on issues and PRs |
| `confidential_note_events` | `issue_comment`, `pull_request_review_comment` | GitHub doesn't differentiate confidential |
| `wiki_page_events` | `gollum` | Wiki events |
| `pipeline_events` | `workflow_run`, `check_suite` | CI/CD pipeline events |
| `job_events` | `workflow_job` | Individual job events |
| `deployment_events` | `deployment`, `deployment_status` | Deployment lifecycle |
| `releases_events` | `release` | Release events |

### Unmappable Events

The following GitLab events have no direct GitHub equivalent and will be reported in warnings:

| GitLab Event | Reason |
|--------------|--------|
| `repository_update_events` | No direct GitHub equivalent |
| `subgroup_events` | GitHub doesn't have subgroups |
| `feature_flag_events` | No direct GitHub equivalent |
| `alert_events` | No direct GitHub equivalent |

## Configuration Mapping

### SSL Verification

- **GitLab**: `enable_ssl_verification: true/false`
- **GitHub**: `insecure_ssl: "0"/"1"` (string, inverted logic)

The transformer automatically handles the conversion:
- GitLab `enable_ssl_verification: true` → GitHub `insecure_ssl: "0"`
- GitLab `enable_ssl_verification: false` → GitHub `insecure_ssl: "1"`

### Webhook Status

- **GitLab**: `disabled: true/false`
- **GitHub**: `active: true/false`

The transformer automatically inverts the GitLab `disabled` flag to GitHub's `active` flag.

### Content Type

Both platforms support `json` and `form` content types. The default is `json`.

## Webhook Secrets

**Important Security Note**: GitLab's API does not return webhook secret values (tokens) for security reasons. Therefore:

1. All webhook secrets are marked as `null` in the export
2. During migration planning, webhooks will require user input for secrets
3. Options for handling secrets:
   - **Generate new secrets**: The system can generate random secrets for GitHub webhooks
   - **Manual configuration**: Update webhook receivers to use new secrets
   - **Skip secret requirement**: Use `${USER_INPUT_REQUIRED}` placeholder

### Security Best Practice

It is recommended to:
1. Generate new secrets for GitHub webhooks
2. Update your webhook-receiving services with the new secrets
3. Deactivate old GitLab webhooks after successful migration
4. Use strong, randomly-generated secrets (minimum 20 characters)

## Migration Process

### 1. Export Stage

Webhooks are exported from GitLab with all configuration:

```json
{
  "id": 12345,
  "url": "https://jenkins.example.com/gitlab/build",
  "push_events": true,
  "merge_requests_events": true,
  "tag_push_events": false,
  "enable_ssl_verification": true,
  "token": "***MASKED***"
}
```

### 2. Transform Stage

The `WebhookTransformer` converts GitLab webhooks to GitHub format:

```json
{
  "id": 1,
  "url": "https://jenkins.example.com/gitlab/build",
  "events": ["push", "pull_request"],
  "active": true,
  "content_type": "json",
  "insecure_ssl": false,
  "secret": null,
  "gitlab_id": 12345,
  "gitlab_events": ["push_events", "merge_requests_events"],
  "unmapped_events": []
}
```

### 3. Plan Stage

The `PlanAgent` generates webhook creation actions:

```json
{
  "type": "webhook_create",
  "parameters": {
    "target_repo": "org/repo",
    "url": "https://jenkins.example.com/gitlab/build",
    "events": ["push", "pull_request"],
    "secret": "${USER_INPUT_REQUIRED}",
    "content_type": "json",
    "active": true
  }
}
```

### 4. Apply Stage

The `CreateWebhookAction` creates the webhook on GitHub using the PyGithub API.

## Gap Analysis

The transformer provides detailed gap analysis for:

1. **Unmappable Events**: Events that don't have GitHub equivalents
2. **Configuration Differences**: Settings that work differently on GitHub
3. **Secret Requirements**: Webhooks requiring new secrets

### Example Gap Report

```json
{
  "webhook_url": "https://example.com/hook",
  "unmapped_events": [
    {
      "gitlab_event": "repository_update_events",
      "reason": "No direct GitHub equivalent"
    }
  ],
  "warnings": [
    "Webhook secret must be regenerated - not available in export"
  ]
}
```

## Testing

The webhook transformation includes comprehensive test coverage:

- **17 Unit Tests** for `WebhookTransformer`
  - Event mapping (push, tags, MRs, issues, etc.)
  - Multiple events per webhook
  - Unmappable events handling
  - SSL verification mapping
  - Secret handling
  - Disabled/active status
  - Edge cases (no events, no URL, etc.)

- **Integration Test** for plan generation
  - Webhook action creation
  - Event transformation validation
  - User input requirement detection
  - Phase organization (INTEGRATIONS phase)

## Limitations and Considerations

### 1. Event Granularity

Some GitLab events are more granular than GitHub events:
- GitLab's `note_events` maps to both `issue_comment` and `pull_request_review_comment`
- This means the webhook receiver may get more notifications than in GitLab

### 2. No Secret Migration

Webhook secrets cannot be migrated and must be regenerated. This is a security feature, not a limitation.

### 3. Webhook URL Compatibility

Ensure your webhook endpoints can handle GitHub's webhook payload format, which differs from GitLab's:
- Different header format (`X-GitHub-Event` vs `X-Gitlab-Event`)
- Different JSON structure
- Different authentication method (HMAC-SHA256 with secret)

### 4. Testing Webhooks

After migration:
1. Test each webhook with GitHub's webhook testing feature
2. Verify webhook receivers handle GitHub payload format
3. Check webhook delivery history in GitHub settings
4. Update any webhook URL paths if needed (e.g., `/gitlab/hook` → `/github/hook`)

## Troubleshooting

### Webhook Not Triggering

1. Check webhook secret is correctly configured
2. Verify webhook is marked as "active" on GitHub
3. Check GitHub webhook delivery history for errors
4. Ensure receiving endpoint accepts GitHub's payload format

### Missing Events

1. Review the gap analysis report for unmappable events
2. Consider using GitHub Apps or Actions for unsupported events
3. Check if the event name was correctly mapped

### SSL Verification Errors

1. Ensure your webhook endpoint has a valid SSL certificate
2. If using self-signed certificates, set `insecure_ssl: true` (not recommended for production)
3. Consider using a reverse proxy with valid SSL for development

## Example: Complete Webhook Migration

### Source (GitLab)

```json
{
  "id": 1,
  "url": "https://ci.example.com/hook",
  "push_events": true,
  "merge_requests_events": true,
  "pipeline_events": true,
  "enable_ssl_verification": true
}
```

### Transformed (GitHub-ready)

```json
{
  "url": "https://ci.example.com/hook",
  "events": ["push", "pull_request", "workflow_run", "check_suite"],
  "config": {
    "url": "https://ci.example.com/hook",
    "content_type": "json",
    "secret": "new-generated-secret-here",
    "insecure_ssl": "0"
  },
  "active": true
}
```

### Result (GitHub)

Webhook created on GitHub repository with:
- URL: `https://ci.example.com/hook`
- Events: push, pull_request, workflow_run, check_suite
- Active: true
- SSL verification: enabled
- Secret: securely stored

## References

- [GitHub Webhooks Documentation](https://docs.github.com/en/developers/webhooks-and-events/webhooks/about-webhooks)
- [GitLab Webhooks Documentation](https://docs.gitlab.com/ee/user/project/integrations/webhooks.html)
- [GitHub Event Types](https://docs.github.com/en/developers/webhooks-and-events/webhooks/webhook-events-and-payloads)
- [GitLab Event Types](https://docs.gitlab.com/ee/user/project/integrations/webhook_events.html)
