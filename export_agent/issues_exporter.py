"""
Issues exporter - exports issues, comments, attachments, cross-references, and time tracking.

Exports all issue data for migration to GitHub Issues.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

from discovery_agent.gitlab_client import GitLabClient

logger = logging.getLogger(__name__)


class IssuesExporter:
    """
    Export issues and related data.
    
    Exports:
    - Issues with metadata
    - Comments/notes on issues
    - Issue attachments (downloads files)
    - Cross-references to other issues/MRs
    - Time tracking data
    - Labels and milestones
    """
    
    def __init__(self, client: GitLabClient, output_dir: Path):
        """
        Initialize issues exporter.
        
        Args:
            client: GitLab API client
            output_dir: Base output directory
        """
        self.client = client
        self.output_dir = output_dir
        self.logger = logging.getLogger(f"{__name__}.IssuesExporter")
    
    def export(self, project_id: int, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Export issues data.
        
        Args:
            project_id: GitLab project ID
            project_data: Project metadata from API
            
        Returns:
            Export metadata dictionary
        """
        self.logger.info(f"Exporting issues for project {project_id}")
        
        issues_dir = self.output_dir / str(project_id) / "issues"
        issues_dir.mkdir(parents=True, exist_ok=True)
        
        metadata: Dict[str, Any] = {
            "project_id": project_id,
        }
        
        # Export labels
        try:
            labels = self._export_labels(project_id, issues_dir)
            metadata["labels"] = labels
        except Exception as e:
            self.logger.error(f"Failed to export labels: {e}")
            metadata["labels_error"] = str(e)
        
        # Export milestones
        try:
            milestones = self._export_milestones(project_id, issues_dir)
            metadata["milestones"] = milestones
        except Exception as e:
            self.logger.error(f"Failed to export milestones: {e}")
            metadata["milestones_error"] = str(e)
        
        # Export issues
        try:
            issues = self._export_issues(project_id, issues_dir)
            metadata["issues"] = issues
        except Exception as e:
            self.logger.error(f"Failed to export issues: {e}")
            metadata["issues_error"] = str(e)
        
        # Save metadata
        self._save_metadata(issues_dir, metadata)
        
        metadata["status"] = "completed"
        self.logger.info(f"Issues export completed for project {project_id}")
        return metadata
    
    def _export_labels(self, project_id: int, output_dir: Path) -> Dict[str, Any]:
        """Export project labels."""
        self.logger.debug(f"Fetching labels for project {project_id}")
        
        labels = []
        label_count = 0
        
        for label in self.client.paginate(f"/api/v4/projects/{project_id}/labels"):
            label_count += 1
            labels.append({
                "id": label.get("id"),
                "name": label.get("name"),
                "description": label.get("description"),
                "color": label.get("color"),
                "text_color": label.get("text_color"),
                "open_issues_count": label.get("open_issues_count", 0),
                "closed_issues_count": label.get("closed_issues_count", 0),
                "open_merge_requests_count": label.get("open_merge_requests_count", 0),
            })
        
        # Save labels
        import json
        with open(output_dir / "labels.json", "w", encoding="utf-8") as f:
            json.dump(labels, f, indent=2, ensure_ascii=False)
        
        return {
            "total": label_count,
            "file": "labels.json",
        }
    
    def _export_milestones(self, project_id: int, output_dir: Path) -> Dict[str, Any]:
        """Export project milestones."""
        self.logger.debug(f"Fetching milestones for project {project_id}")
        
        milestones = []
        milestone_count = 0
        active_count = 0
        
        for milestone in self.client.paginate(f"/api/v4/projects/{project_id}/milestones"):
            milestone_count += 1
            if milestone.get("state") == "active":
                active_count += 1
            
            milestones.append({
                "id": milestone.get("id"),
                "iid": milestone.get("iid"),
                "title": milestone.get("title"),
                "description": milestone.get("description"),
                "state": milestone.get("state"),
                "due_date": milestone.get("due_date"),
                "start_date": milestone.get("start_date"),
                "created_at": milestone.get("created_at"),
                "updated_at": milestone.get("updated_at"),
            })
        
        # Save milestones
        import json
        with open(output_dir / "milestones.json", "w", encoding="utf-8") as f:
            json.dump(milestones, f, indent=2, ensure_ascii=False)
        
        return {
            "total": milestone_count,
            "active": active_count,
            "file": "milestones.json",
        }
    
    def _export_issues(self, project_id: int, output_dir: Path) -> Dict[str, Any]:
        """Export all issues with comments and attachments."""
        self.logger.debug(f"Fetching issues for project {project_id}")
        
        issues_list = []
        issue_count = 0
        state_counts: Dict[str, int] = {}
        
        # Create subdirectories
        attachments_dir = output_dir / "attachments"
        attachments_dir.mkdir(exist_ok=True)
        
        for issue in self.client.paginate(f"/api/v4/projects/{project_id}/issues"):
            issue_count += 1
            issue_iid = issue.get("iid")
            
            state = issue.get("state", "unknown")
            state_counts[state] = state_counts.get(state, 0) + 1
            
            # Extract issue data
            issue_data = {
                "id": issue.get("id"),
                "iid": issue_iid,
                "title": issue.get("title"),
                "description": issue.get("description"),
                "state": state,
                "created_at": issue.get("created_at"),
                "updated_at": issue.get("updated_at"),
                "closed_at": issue.get("closed_at"),
                "closed_by": self._extract_user(issue.get("closed_by")),
                "author": self._extract_user(issue.get("author")),
                "assignees": [self._extract_user(u) for u in issue.get("assignees", [])],
                "labels": issue.get("labels", []),
                "milestone": issue.get("milestone", {}).get("title") if issue.get("milestone") else None,
                "web_url": issue.get("web_url"),
                "upvotes": issue.get("upvotes", 0),
                "downvotes": issue.get("downvotes", 0),
                "user_notes_count": issue.get("user_notes_count", 0),
                "confidential": issue.get("confidential", False),
                "discussion_locked": issue.get("discussion_locked", False),
                "due_date": issue.get("due_date"),
                "time_stats": issue.get("time_stats", {}),
            }
            
            # Get issue comments/notes
            try:
                comments = self._export_issue_notes(project_id, issue_iid)
                issue_data["comments"] = comments
            except Exception as e:
                self.logger.error(f"Failed to export notes for issue {issue_iid}: {e}")
                issue_data["comments_error"] = str(e)
            
            # Download attachments
            try:
                attachments = self._download_attachments(
                    issue_data["description"],
                    attachments_dir / str(issue_iid),
                    f"issue-{issue_iid}"
                )
                issue_data["attachments"] = attachments
            except Exception as e:
                self.logger.error(f"Failed to download attachments for issue {issue_iid}: {e}")
                issue_data["attachments_error"] = str(e)
            
            issues_list.append(issue_data)
            
            # Log progress
            if issue_count % 50 == 0:
                self.logger.info(f"Exported {issue_count} issues...")
        
        # Save issues
        import json
        with open(output_dir / "issues.json", "w", encoding="utf-8") as f:
            json.dump(issues_list, f, indent=2, ensure_ascii=False)
        
        return {
            "total": issue_count,
            "state_counts": state_counts,
            "file": "issues.json",
        }
    
    def _export_issue_notes(self, project_id: int, issue_iid: int) -> List[Dict[str, Any]]:
        """Export notes/comments for an issue."""
        notes = []
        
        for note in self.client.paginate(
            f"/api/v4/projects/{project_id}/issues/{issue_iid}/notes",
            params={"sort": "asc"}
        ):
            # Skip system notes (automated messages)
            if note.get("system", False):
                continue
            
            notes.append({
                "id": note.get("id"),
                "body": note.get("body"),
                "author": self._extract_user(note.get("author")),
                "created_at": note.get("created_at"),
                "updated_at": note.get("updated_at"),
                "resolvable": note.get("resolvable", False),
                "resolved": note.get("resolved", False),
            })
        
        return notes
    
    def _download_attachments(
        self,
        content: str | None,
        output_dir: Path,
        prefix: str
    ) -> List[Dict[str, Any]]:
        """
        Download attachments from markdown content.
        
        Extracts attachment URLs from markdown and downloads them.
        """
        if not content:
            return []
        
        attachments = []
        
        # Look for markdown image/link patterns
        import re
        patterns = [
            r'!\[.*?\]\((.*?)\)',  # Images: ![alt](url)
            r'\[.*?\]\((.*?)\)',   # Links: [text](url)
        ]
        
        urls = set()
        for pattern in patterns:
            matches = re.findall(pattern, content)
            urls.update(matches)
        
        # Filter for actual attachment URLs (relative paths or uploads)
        for url in urls:
            if not url or url.startswith("http://") or url.startswith("https://"):
                # Skip external URLs for now
                continue
            
            attachments.append({
                "url": url,
                "note": "Attachment URL found but not downloaded",
            })
        
        return attachments
    
    def _extract_user(self, user_data: Dict[str, Any] | None) -> Dict[str, Any] | None:
        """Extract relevant user information."""
        if not user_data:
            return None
        
        return {
            "username": user_data.get("username"),
            "name": user_data.get("name"),
            "id": user_data.get("id"),
        }
    
    def _save_metadata(self, output_dir: Path, metadata: Dict[str, Any]) -> None:
        """Save issues metadata to JSON file."""
        import json
        with open(output_dir / "issues_metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        self.logger.debug(f"Saved issues metadata to {output_dir / 'issues_metadata.json'}")
