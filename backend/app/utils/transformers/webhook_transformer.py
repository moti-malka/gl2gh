"""Webhook transformer - Convert GitLab webhooks to GitHub webhooks"""

from typing import Any, Dict, List
from .base_transformer import BaseTransformer, TransformationResult


class WebhookTransformer(BaseTransformer):
    """
    Transform GitLab webhooks to GitHub webhooks.
    
    Handles:
    - Event type mapping (GitLab events -> GitHub events)
    - Configuration transformation
    - Gap identification for unmappable events
    """
    
    # Event mapping from GitLab to GitHub
    EVENT_MAPPING = {
        "push_events": ["push"],
        "tag_push_events": ["create"],  # GitHub uses 'create' for tags
        "issues_events": ["issues"],
        "confidential_issues_events": ["issues"],  # GitHub doesn't have confidential issues
        "merge_requests_events": ["pull_request"],
        "note_events": ["issue_comment", "pull_request_review_comment"],
        "confidential_note_events": ["issue_comment", "pull_request_review_comment"],
        "wiki_page_events": ["gollum"],
        "pipeline_events": ["workflow_run", "check_suite"],
        "job_events": ["workflow_job"],
        "deployment_events": ["deployment", "deployment_status"],
        "releases_events": ["release"],
    }
    
    # Events that don't have direct GitHub equivalents
    UNMAPPABLE_EVENTS = {
        "repository_update_events": "No direct GitHub equivalent",
        "subgroup_events": "GitHub doesn't have subgroups",
        "feature_flag_events": "No direct GitHub equivalent",
        "alert_events": "No direct GitHub equivalent",
    }
    
    def __init__(self):
        """Initialize webhook transformer"""
        super().__init__(name="WebhookTransformer")
    
    def transform(self, input_data: Dict[str, Any]) -> TransformationResult:
        """
        Transform GitLab webhooks to GitHub format.
        
        Args:
            input_data: Dict with 'webhooks' key containing list of GitLab webhooks
            
        Returns:
            TransformationResult with transformed webhooks
        """
        self.log_transform_start("webhooks")
        
        webhooks = input_data.get("webhooks", [])
        if not webhooks:
            self.logger.info("No webhooks to transform")
            return TransformationResult(
                success=True,
                data={"webhooks": []},
                metadata={"webhook_count": 0}
            )
        
        result = TransformationResult(success=True, data={"webhooks": []})
        transformed_count = 0
        
        for webhook in webhooks:
            try:
                transformed = self._transform_webhook(webhook, result)
                if transformed:
                    result.data["webhooks"].append(transformed)
                    transformed_count += 1
            except Exception as e:
                result.add_error(
                    f"Failed to transform webhook: {str(e)}",
                    {"webhook_url": webhook.get("url", "unknown")}
                )
        
        result.metadata["webhook_count"] = len(webhooks)
        result.metadata["transformed_count"] = transformed_count
        result.metadata["skipped_count"] = len(webhooks) - transformed_count
        
        self.log_transform_complete(result.success, f"{transformed_count}/{len(webhooks)} webhooks")
        
        return result
    
    def _transform_webhook(
        self,
        gitlab_webhook: Dict[str, Any],
        result: TransformationResult
    ) -> Dict[str, Any]:
        """
        Transform a single webhook.
        
        Args:
            gitlab_webhook: GitLab webhook data
            result: TransformationResult to add warnings/errors
            
        Returns:
            Transformed webhook data for GitHub
        """
        url = gitlab_webhook.get("url")
        if not url:
            result.add_error("Webhook missing URL", {"webhook_id": gitlab_webhook.get("id")})
            return None
        
        # Map GitLab events to GitHub events
        github_events = []
        unmapped_events = []
        
        for gitlab_event, enabled in gitlab_webhook.items():
            if not gitlab_event.endswith("_events"):
                continue
            
            if not enabled:
                continue
            
            # Check if event is mappable
            if gitlab_event in self.EVENT_MAPPING:
                github_events.extend(self.EVENT_MAPPING[gitlab_event])
            elif gitlab_event in self.UNMAPPABLE_EVENTS:
                unmapped_events.append({
                    "gitlab_event": gitlab_event,
                    "reason": self.UNMAPPABLE_EVENTS[gitlab_event]
                })
            else:
                # Unknown event type
                result.add_warning(
                    f"Unknown GitLab webhook event type: {gitlab_event}",
                    {"webhook_url": url}
                )
        
        # Remove duplicates and sort
        github_events = sorted(list(set(github_events)))
        
        # Default to push if no events are mapped
        if not github_events:
            github_events = ["push"]
            result.add_warning(
                "No events mapped from GitLab, defaulting to 'push'",
                {"webhook_url": url}
            )
        
        # Add warnings for unmapped events
        for unmapped in unmapped_events:
            result.add_warning(
                f"GitLab event '{unmapped['gitlab_event']}' cannot be mapped: {unmapped['reason']}",
                {"webhook_url": url}
            )
        
        # Build transformed webhook
        transformed = {
            "id": gitlab_webhook.get("id"),
            "url": url,
            "events": github_events,
            "active": not gitlab_webhook.get("disabled", False),
            "content_type": "json",  # GitHub default
            "insecure_ssl": not gitlab_webhook.get("enable_ssl_verification", True),
            
            # Metadata for tracking
            "gitlab_id": gitlab_webhook.get("id"),
            "gitlab_url": url,
            "gitlab_events": [
                event for event, enabled in gitlab_webhook.items()
                if event.endswith("_events") and enabled
            ],
            "unmapped_events": unmapped_events
        }
        
        # Note about secrets
        if "token" in gitlab_webhook and gitlab_webhook["token"] != "***MASKED***":
            # Unlikely to happen as GitLab API doesn't return token values
            result.add_warning(
                "Webhook secret found in export (unexpected). Secrets should be regenerated.",
                {"webhook_url": url}
            )
        else:
            # Expected case - no secret available
            transformed["secret"] = None  # Will require user input or generation
        
        return transformed
