"""
Settings exporter - exports branch/tag protections, members, webhooks, deploy keys, and project settings.

Exports all project configuration and settings for migration.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from discovery_agent.gitlab_client import GitLabClient

logger = logging.getLogger(__name__)


class SettingsExporter:
    """
    Export project settings and configuration.
    
    Exports:
    - Branch protection rules
    - Tag protection rules
    - Project members and access levels
    - Webhooks (metadata only, not secrets)
    - Deploy keys
    - Project settings (visibility, features, etc.)
    - Deploy tokens (metadata only)
    """
    
    def __init__(self, client: GitLabClient, output_dir: Path):
        """
        Initialize settings exporter.
        
        Args:
            client: GitLab API client
            output_dir: Base output directory
        """
        self.client = client
        self.output_dir = output_dir
        self.logger = logging.getLogger(f"{__name__}.SettingsExporter")
    
    def export(self, project_id: int, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Export settings data.
        
        Args:
            project_id: GitLab project ID
            project_data: Project metadata from API
            
        Returns:
            Export metadata dictionary
        """
        self.logger.info(f"Exporting settings for project {project_id}")
        
        settings_dir = self.output_dir / str(project_id) / "settings"
        settings_dir.mkdir(parents=True, exist_ok=True)
        
        metadata: Dict[str, Any] = {
            "project_id": project_id,
        }
        
        # Export project settings
        try:
            project_settings = self._export_project_settings(project_data)
            metadata["project_settings"] = project_settings
            self._save_json(settings_dir / "project_settings.json", project_settings)
        except Exception as e:
            self.logger.error(f"Failed to export project settings: {e}")
            metadata["project_settings_error"] = str(e)
        
        # Export branch protections
        try:
            branch_protections = self._export_branch_protections(project_id, settings_dir)
            metadata["branch_protections"] = branch_protections
        except Exception as e:
            self.logger.error(f"Failed to export branch protections: {e}")
            metadata["branch_protections_error"] = str(e)
        
        # Export tag protections
        try:
            tag_protections = self._export_tag_protections(project_id, settings_dir)
            metadata["tag_protections"] = tag_protections
        except Exception as e:
            self.logger.error(f"Failed to export tag protections: {e}")
            metadata["tag_protections_error"] = str(e)
        
        # Export members
        try:
            members = self._export_members(project_id, settings_dir)
            metadata["members"] = members
        except Exception as e:
            self.logger.error(f"Failed to export members: {e}")
            metadata["members_error"] = str(e)
        
        # Export webhooks
        try:
            webhooks = self._export_webhooks(project_id, settings_dir)
            metadata["webhooks"] = webhooks
        except Exception as e:
            self.logger.error(f"Failed to export webhooks: {e}")
            metadata["webhooks_error"] = str(e)
        
        # Export deploy keys
        try:
            deploy_keys = self._export_deploy_keys(project_id, settings_dir)
            metadata["deploy_keys"] = deploy_keys
        except Exception as e:
            self.logger.error(f"Failed to export deploy keys: {e}")
            metadata["deploy_keys_error"] = str(e)
        
        # Export deploy tokens
        try:
            deploy_tokens = self._export_deploy_tokens(project_id, settings_dir)
            metadata["deploy_tokens"] = deploy_tokens
        except Exception as e:
            self.logger.error(f"Failed to export deploy tokens: {e}")
            metadata["deploy_tokens_error"] = str(e)
        
        # Save metadata
        self._save_metadata(settings_dir, metadata)
        
        metadata["status"] = "completed"
        self.logger.info(f"Settings export completed for project {project_id}")
        return metadata
    
    def _export_project_settings(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """Export core project settings."""
        return {
            "name": project_data.get("name"),
            "path": project_data.get("path"),
            "description": project_data.get("description"),
            "visibility": project_data.get("visibility"),
            "default_branch": project_data.get("default_branch"),
            "topics": project_data.get("topics", []),
            "archived": project_data.get("archived", False),
            "issues_enabled": project_data.get("issues_enabled", True),
            "merge_requests_enabled": project_data.get("merge_requests_enabled", True),
            "wiki_enabled": project_data.get("wiki_enabled", True),
            "snippets_enabled": project_data.get("snippets_enabled", True),
            "container_registry_enabled": project_data.get("container_registry_enabled", False),
            "packages_enabled": project_data.get("packages_enabled", False),
            "only_allow_merge_if_pipeline_succeeds": project_data.get("only_allow_merge_if_pipeline_succeeds", False),
            "only_allow_merge_if_all_discussions_are_resolved": project_data.get("only_allow_merge_if_all_discussions_are_resolved", False),
            "autoclose_referenced_issues": project_data.get("autoclose_referenced_issues", True),
            "remove_source_branch_after_merge": project_data.get("remove_source_branch_after_merge", False),
            "request_access_enabled": project_data.get("request_access_enabled", True),
            "suggestion_commit_message": project_data.get("suggestion_commit_message"),
            "merge_method": project_data.get("merge_method", "merge"),
            "squash_option": project_data.get("squash_option", "default_off"),
            "ci_config_path": project_data.get("ci_config_path"),
            "build_git_strategy": project_data.get("build_git_strategy", "fetch"),
            "build_timeout": project_data.get("build_timeout", 3600),
            "auto_cancel_pending_pipelines": project_data.get("auto_cancel_pending_pipelines", "enabled"),
            "ci_default_git_depth": project_data.get("ci_default_git_depth", 50),
            "public_jobs": project_data.get("public_jobs", True),
            "emails_disabled": project_data.get("emails_disabled", False),
        }
    
    def _export_branch_protections(self, project_id: int, output_dir: Path) -> Dict[str, Any]:
        """Export protected branches."""
        self.logger.debug(f"Fetching protected branches for project {project_id}")
        
        protections = []
        protection_count = 0
        
        for protection in self.client.paginate(f"/api/v4/projects/{project_id}/protected_branches"):
            protection_count += 1
            protections.append({
                "name": protection.get("name"),
                "push_access_levels": [
                    {
                        "access_level": pal.get("access_level"),
                        "access_level_description": pal.get("access_level_description"),
                    }
                    for pal in protection.get("push_access_levels", [])
                ],
                "merge_access_levels": [
                    {
                        "access_level": mal.get("access_level"),
                        "access_level_description": mal.get("access_level_description"),
                    }
                    for mal in protection.get("merge_access_levels", [])
                ],
                "allow_force_push": protection.get("allow_force_push", False),
                "code_owner_approval_required": protection.get("code_owner_approval_required", False),
            })
        
        # Save protections
        self._save_json(output_dir / "protected_branches.json", protections)
        
        return {
            "total": protection_count,
            "file": "protected_branches.json",
        }
    
    def _export_tag_protections(self, project_id: int, output_dir: Path) -> Dict[str, Any]:
        """Export protected tags."""
        self.logger.debug(f"Fetching protected tags for project {project_id}")
        
        protections = []
        protection_count = 0
        
        for protection in self.client.paginate(f"/api/v4/projects/{project_id}/protected_tags"):
            protection_count += 1
            protections.append({
                "name": protection.get("name"),
                "create_access_levels": [
                    {
                        "access_level": cal.get("access_level"),
                        "access_level_description": cal.get("access_level_description"),
                    }
                    for cal in protection.get("create_access_levels", [])
                ],
            })
        
        # Save protections
        self._save_json(output_dir / "protected_tags.json", protections)
        
        return {
            "total": protection_count,
            "file": "protected_tags.json",
        }
    
    def _export_members(self, project_id: int, output_dir: Path) -> Dict[str, Any]:
        """Export project members."""
        self.logger.debug(f"Fetching members for project {project_id}")
        
        members = []
        member_count = 0
        access_levels: Dict[int, int] = {}
        
        for member in self.client.paginate(f"/api/v4/projects/{project_id}/members/all"):
            member_count += 1
            access_level = member.get("access_level", 0)
            access_levels[access_level] = access_levels.get(access_level, 0) + 1
            
            members.append({
                "id": member.get("id"),
                "username": member.get("username"),
                "name": member.get("name"),
                "access_level": access_level,
                "expires_at": member.get("expires_at"),
            })
        
        # Save members
        self._save_json(output_dir / "members.json", members)
        
        # Access level mapping: 10=Guest, 20=Reporter, 30=Developer, 40=Maintainer, 50=Owner
        access_level_names = {
            10: "Guest",
            20: "Reporter",
            30: "Developer",
            40: "Maintainer",
            50: "Owner",
        }
        
        return {
            "total": member_count,
            "access_levels": {
                access_level_names.get(level, f"Level_{level}"): count
                for level, count in access_levels.items()
            },
            "file": "members.json",
        }
    
    def _export_webhooks(self, project_id: int, output_dir: Path) -> Dict[str, Any]:
        """Export webhooks (metadata only, not tokens)."""
        self.logger.debug(f"Fetching webhooks for project {project_id}")
        
        webhooks = []
        webhook_count = 0
        
        for webhook in self.client.paginate(f"/api/v4/projects/{project_id}/hooks"):
            webhook_count += 1
            webhooks.append({
                "id": webhook.get("id"),
                "url": webhook.get("url"),
                "push_events": webhook.get("push_events", False),
                "issues_events": webhook.get("issues_events", False),
                "merge_requests_events": webhook.get("merge_requests_events", False),
                "wiki_page_events": webhook.get("wiki_page_events", False),
                "tag_push_events": webhook.get("tag_push_events", False),
                "note_events": webhook.get("note_events", False),
                "job_events": webhook.get("job_events", False),
                "pipeline_events": webhook.get("pipeline_events", False),
                "deployment_events": webhook.get("deployment_events", False),
                "releases_events": webhook.get("releases_events", False),
                "enable_ssl_verification": webhook.get("enable_ssl_verification", True),
                "created_at": webhook.get("created_at"),
                "note": "Token/secret not exported for security",
            })
        
        # Save webhooks
        self._save_json(output_dir / "webhooks.json", webhooks)
        
        return {
            "total": webhook_count,
            "file": "webhooks.json",
        }
    
    def _export_deploy_keys(self, project_id: int, output_dir: Path) -> Dict[str, Any]:
        """Export deploy keys."""
        self.logger.debug(f"Fetching deploy keys for project {project_id}")
        
        deploy_keys = []
        key_count = 0
        
        for key in self.client.paginate(f"/api/v4/projects/{project_id}/deploy_keys"):
            key_count += 1
            deploy_keys.append({
                "id": key.get("id"),
                "title": key.get("title"),
                "key": key.get("key"),
                "can_push": key.get("can_push", False),
                "created_at": key.get("created_at"),
            })
        
        # Save deploy keys
        self._save_json(output_dir / "deploy_keys.json", deploy_keys)
        
        return {
            "total": key_count,
            "file": "deploy_keys.json",
        }
    
    def _export_deploy_tokens(self, project_id: int, output_dir: Path) -> Dict[str, Any]:
        """Export deploy tokens (metadata only, not token values)."""
        self.logger.debug(f"Fetching deploy tokens for project {project_id}")
        
        # Note: GitLab API may not return all deploy tokens depending on permissions
        status_code, data, _ = self.client.get(
            f"/api/v4/projects/{project_id}/deploy_tokens"
        )
        
        if status_code != 200:
            return {
                "total": 0,
                "note": "Deploy tokens API not accessible or not available",
            }
        
        deploy_tokens = []
        token_count = 0
        
        if isinstance(data, list):
            for token in data:
                token_count += 1
                deploy_tokens.append({
                    "id": token.get("id"),
                    "name": token.get("name"),
                    "username": token.get("username"),
                    "expires_at": token.get("expires_at"),
                    "scopes": token.get("scopes", []),
                    "revoked": token.get("revoked", False),
                    "note": "Token value not exported for security",
                })
        
        # Save deploy tokens
        self._save_json(output_dir / "deploy_tokens.json", deploy_tokens)
        
        return {
            "total": token_count,
            "file": "deploy_tokens.json",
        }
    
    def _save_json(self, path: Path, data: Any) -> None:
        """Save data to JSON file."""
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _save_metadata(self, output_dir: Path, metadata: Dict[str, Any]) -> None:
        """Save settings metadata to JSON file."""
        import json
        with open(output_dir / "settings_metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        self.logger.debug(f"Saved settings metadata to {output_dir / 'settings_metadata.json'}")
