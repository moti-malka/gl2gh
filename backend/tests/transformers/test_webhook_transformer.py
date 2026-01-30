"""Tests for webhook transformer"""

import pytest
from app.utils.transformers import WebhookTransformer


class TestWebhookTransformer:
    """Test cases for GitLab to GitHub webhook transformation"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.transformer = WebhookTransformer()
    
    def test_basic_webhook_transformation(self):
        """Test basic webhook transformation with push events"""
        gitlab_webhooks = [
            {
                "id": 1,
                "url": "https://example.com/webhook",
                "push_events": True,
                "merge_requests_events": False,
                "issues_events": False,
                "enable_ssl_verification": True
            }
        ]
        
        result = self.transformer.transform({"webhooks": gitlab_webhooks})
        
        assert result.success
        webhooks = result.data["webhooks"]
        assert len(webhooks) == 1
        
        webhook = webhooks[0]
        assert webhook["url"] == "https://example.com/webhook"
        assert "push" in webhook["events"]
        assert webhook["active"] is True
        assert webhook["insecure_ssl"] is False
    
    def test_multiple_events_mapping(self):
        """Test webhook with multiple GitLab events mapped to GitHub"""
        gitlab_webhooks = [
            {
                "id": 2,
                "url": "https://example.com/ci-webhook",
                "push_events": True,
                "tag_push_events": True,
                "merge_requests_events": True,
                "issues_events": True,
                "wiki_page_events": True,
                "enable_ssl_verification": True
            }
        ]
        
        result = self.transformer.transform({"webhooks": gitlab_webhooks})
        
        assert result.success
        webhooks = result.data["webhooks"]
        assert len(webhooks) == 1
        
        webhook = webhooks[0]
        events = webhook["events"]
        
        # Check mapped events
        assert "push" in events
        assert "create" in events  # tag_push_events -> create
        assert "pull_request" in events  # merge_requests_events
        assert "issues" in events
        assert "gollum" in events  # wiki_page_events
    
    def test_note_events_mapping(self):
        """Test note events mapping to multiple GitHub comment events"""
        gitlab_webhooks = [
            {
                "id": 3,
                "url": "https://example.com/comments",
                "note_events": True,
                "enable_ssl_verification": True
            }
        ]
        
        result = self.transformer.transform({"webhooks": gitlab_webhooks})
        
        assert result.success
        webhook = result.data["webhooks"][0]
        
        # note_events should map to both issue_comment and pull_request_review_comment
        assert "issue_comment" in webhook["events"]
        assert "pull_request_review_comment" in webhook["events"]
    
    def test_pipeline_events_mapping(self):
        """Test pipeline events mapping to GitHub workflow events"""
        gitlab_webhooks = [
            {
                "id": 4,
                "url": "https://example.com/pipelines",
                "pipeline_events": True,
                "enable_ssl_verification": True
            }
        ]
        
        result = self.transformer.transform({"webhooks": gitlab_webhooks})
        
        assert result.success
        webhook = result.data["webhooks"][0]
        
        # pipeline_events should map to workflow_run and check_suite
        assert "workflow_run" in webhook["events"]
        assert "check_suite" in webhook["events"]
    
    def test_unmappable_events_warning(self):
        """Test that unmappable events generate warnings"""
        gitlab_webhooks = [
            {
                "id": 5,
                "url": "https://example.com/special",
                "push_events": True,
                "repository_update_events": True,  # Not mappable to GitHub
                "enable_ssl_verification": True
            }
        ]
        
        result = self.transformer.transform({"webhooks": gitlab_webhooks})
        
        assert result.success
        webhook = result.data["webhooks"][0]
        
        # Should have push event
        assert "push" in webhook["events"]
        
        # Should have unmapped events recorded
        assert len(webhook["unmapped_events"]) > 0
        assert any("repository_update_events" in str(e) for e in webhook["unmapped_events"])
        
        # Should have warning
        assert len(result.warnings) > 0
    
    def test_disabled_webhook(self):
        """Test disabled webhook transformation"""
        gitlab_webhooks = [
            {
                "id": 6,
                "url": "https://example.com/disabled",
                "push_events": True,
                "disabled": True,
                "enable_ssl_verification": True
            }
        ]
        
        result = self.transformer.transform({"webhooks": gitlab_webhooks})
        
        assert result.success
        webhook = result.data["webhooks"][0]
        assert webhook["active"] is False
    
    def test_ssl_verification_disabled(self):
        """Test webhook with SSL verification disabled"""
        gitlab_webhooks = [
            {
                "id": 7,
                "url": "https://example.com/insecure",
                "push_events": True,
                "enable_ssl_verification": False
            }
        ]
        
        result = self.transformer.transform({"webhooks": gitlab_webhooks})
        
        assert result.success
        webhook = result.data["webhooks"][0]
        assert webhook["insecure_ssl"] is True
    
    def test_no_events_defaults_to_push(self):
        """Test webhook with no enabled events defaults to push"""
        gitlab_webhooks = [
            {
                "id": 8,
                "url": "https://example.com/no-events",
                "push_events": False,
                "merge_requests_events": False,
                "enable_ssl_verification": True
            }
        ]
        
        result = self.transformer.transform({"webhooks": gitlab_webhooks})
        
        assert result.success
        webhook = result.data["webhooks"][0]
        assert webhook["events"] == ["push"]
        
        # Should have warning about defaulting
        assert len(result.warnings) > 0
    
    def test_empty_webhooks_list(self):
        """Test transformation with no webhooks"""
        result = self.transformer.transform({"webhooks": []})
        
        assert result.success
        assert len(result.data["webhooks"]) == 0
        assert result.metadata["webhook_count"] == 0
    
    def test_webhook_without_url(self):
        """Test webhook missing URL generates error"""
        gitlab_webhooks = [
            {
                "id": 9,
                "push_events": True,
                "enable_ssl_verification": True
                # No URL field
            }
        ]
        
        result = self.transformer.transform({"webhooks": gitlab_webhooks})
        
        # Should still succeed overall but with errors
        assert len(result.errors) > 0
        assert len(result.data["webhooks"]) == 0
    
    def test_deployment_events_mapping(self):
        """Test deployment events mapping"""
        gitlab_webhooks = [
            {
                "id": 10,
                "url": "https://example.com/deployments",
                "deployment_events": True,
                "enable_ssl_verification": True
            }
        ]
        
        result = self.transformer.transform({"webhooks": gitlab_webhooks})
        
        assert result.success
        webhook = result.data["webhooks"][0]
        
        # deployment_events should map to deployment and deployment_status
        assert "deployment" in webhook["events"]
        assert "deployment_status" in webhook["events"]
    
    def test_releases_events_mapping(self):
        """Test releases events mapping"""
        gitlab_webhooks = [
            {
                "id": 11,
                "url": "https://example.com/releases",
                "releases_events": True,
                "enable_ssl_verification": True
            }
        ]
        
        result = self.transformer.transform({"webhooks": gitlab_webhooks})
        
        assert result.success
        webhook = result.data["webhooks"][0]
        assert "release" in webhook["events"]
    
    def test_confidential_events_mapping(self):
        """Test confidential issues/notes events mapping"""
        gitlab_webhooks = [
            {
                "id": 12,
                "url": "https://example.com/confidential",
                "confidential_issues_events": True,
                "confidential_note_events": True,
                "enable_ssl_verification": True
            }
        ]
        
        result = self.transformer.transform({"webhooks": gitlab_webhooks})
        
        assert result.success
        webhook = result.data["webhooks"][0]
        
        # Confidential events should map to regular GitHub events
        # (GitHub doesn't have confidential issues)
        assert "issues" in webhook["events"]
        assert "issue_comment" in webhook["events"]
        assert "pull_request_review_comment" in webhook["events"]
    
    def test_job_events_mapping(self):
        """Test job events mapping"""
        gitlab_webhooks = [
            {
                "id": 13,
                "url": "https://example.com/jobs",
                "job_events": True,
                "enable_ssl_verification": True
            }
        ]
        
        result = self.transformer.transform({"webhooks": gitlab_webhooks})
        
        assert result.success
        webhook = result.data["webhooks"][0]
        assert "workflow_job" in webhook["events"]
    
    def test_gitlab_metadata_preserved(self):
        """Test that GitLab metadata is preserved in transformed webhook"""
        gitlab_webhooks = [
            {
                "id": 14,
                "url": "https://example.com/metadata",
                "push_events": True,
                "merge_requests_events": True,
                "enable_ssl_verification": True
            }
        ]
        
        result = self.transformer.transform({"webhooks": gitlab_webhooks})
        
        assert result.success
        webhook = result.data["webhooks"][0]
        
        # Check metadata is preserved
        assert webhook["gitlab_id"] == 14
        assert webhook["gitlab_url"] == "https://example.com/metadata"
        assert "push_events" in webhook["gitlab_events"]
        assert "merge_requests_events" in webhook["gitlab_events"]
    
    def test_duplicate_events_removed(self):
        """Test that duplicate events are removed from final list"""
        gitlab_webhooks = [
            {
                "id": 15,
                "url": "https://example.com/dupes",
                # Both note events map to issue_comment and pull_request_review_comment
                "note_events": True,
                "confidential_note_events": True,
                "enable_ssl_verification": True
            }
        ]
        
        result = self.transformer.transform({"webhooks": gitlab_webhooks})
        
        assert result.success
        webhook = result.data["webhooks"][0]
        
        # Should not have duplicates
        events = webhook["events"]
        assert len(events) == len(set(events))
        assert "issue_comment" in events
        assert "pull_request_review_comment" in events
    
    def test_secret_handling(self):
        """Test secret is always set to None (not available from GitLab API)"""
        gitlab_webhooks = [
            {
                "id": 16,
                "url": "https://example.com/secret",
                "push_events": True,
                "token": "***MASKED***",  # Masked token from export
                "enable_ssl_verification": True
            }
        ]
        
        result = self.transformer.transform({"webhooks": gitlab_webhooks})
        
        assert result.success
        webhook = result.data["webhooks"][0]
        assert webhook["secret"] is None
