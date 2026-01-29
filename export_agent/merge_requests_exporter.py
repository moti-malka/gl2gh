"""
Merge requests exporter - exports MRs, discussions, diffs, and approvals.

Exports all merge request data for migration to GitHub Pull Requests.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from discovery_agent.gitlab_client import GitLabClient

logger = logging.getLogger(__name__)


class MergeRequestsExporter:
    """
    Export merge requests and related data.
    
    Exports:
    - Merge requests with metadata
    - Discussions/comments on MRs
    - Diff information
    - Approvals and approval rules
    - Review states
    """
    
    def __init__(self, client: GitLabClient, output_dir: Path):
        """
        Initialize merge requests exporter.
        
        Args:
            client: GitLab API client
            output_dir: Base output directory
        """
        self.client = client
        self.output_dir = output_dir
        self.logger = logging.getLogger(f"{__name__}.MergeRequestsExporter")
    
    def export(self, project_id: int, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Export merge requests data.
        
        Args:
            project_id: GitLab project ID
            project_data: Project metadata from API
            
        Returns:
            Export metadata dictionary
        """
        self.logger.info(f"Exporting merge requests for project {project_id}")
        
        mr_dir = self.output_dir / str(project_id) / "merge_requests"
        mr_dir.mkdir(parents=True, exist_ok=True)
        
        metadata: Dict[str, Any] = {
            "project_id": project_id,
        }
        
        # Export merge requests
        try:
            merge_requests = self._export_merge_requests(project_id, mr_dir)
            metadata["merge_requests"] = merge_requests
        except Exception as e:
            self.logger.error(f"Failed to export merge requests: {e}")
            metadata["merge_requests_error"] = str(e)
        
        # Save metadata
        self._save_metadata(mr_dir, metadata)
        
        metadata["status"] = "completed"
        self.logger.info(f"Merge requests export completed for project {project_id}")
        return metadata
    
    def _export_merge_requests(self, project_id: int, output_dir: Path) -> Dict[str, Any]:
        """Export all merge requests with discussions and approvals."""
        self.logger.debug(f"Fetching merge requests for project {project_id}")
        
        mrs_list = []
        mr_count = 0
        state_counts: Dict[str, int] = {}
        
        for mr in self.client.paginate(f"/api/v4/projects/{project_id}/merge_requests"):
            mr_count += 1
            mr_iid = mr.get("iid")
            
            state = mr.get("state", "unknown")
            state_counts[state] = state_counts.get(state, 0) + 1
            
            # Extract MR data
            mr_data = {
                "id": mr.get("id"),
                "iid": mr_iid,
                "title": mr.get("title"),
                "description": mr.get("description"),
                "state": state,
                "merged_at": mr.get("merged_at"),
                "closed_at": mr.get("closed_at"),
                "created_at": mr.get("created_at"),
                "updated_at": mr.get("updated_at"),
                "target_branch": mr.get("target_branch"),
                "source_branch": mr.get("source_branch"),
                "author": self._extract_user(mr.get("author")),
                "assignees": [self._extract_user(u) for u in mr.get("assignees", [])],
                "reviewers": [self._extract_user(u) for u in mr.get("reviewers", [])],
                "labels": mr.get("labels", []),
                "milestone": mr.get("milestone", {}).get("title") if mr.get("milestone") else None,
                "web_url": mr.get("web_url"),
                "upvotes": mr.get("upvotes", 0),
                "downvotes": mr.get("downvotes", 0),
                "merge_status": mr.get("merge_status"),
                "draft": mr.get("draft", False),
                "work_in_progress": mr.get("work_in_progress", False),
                "discussion_locked": mr.get("discussion_locked", False),
                "has_conflicts": mr.get("has_conflicts", False),
                "sha": mr.get("sha"),
                "merge_commit_sha": mr.get("merge_commit_sha"),
                "squash": mr.get("squash", False),
                "squash_commit_sha": mr.get("squash_commit_sha"),
                "user_notes_count": mr.get("user_notes_count", 0),
                "changes_count": mr.get("changes_count"),
                "should_remove_source_branch": mr.get("should_remove_source_branch"),
                "force_remove_source_branch": mr.get("force_remove_source_branch"),
            }
            
            # Get MR discussions
            try:
                discussions = self._export_mr_discussions(project_id, mr_iid)
                mr_data["discussions"] = discussions
            except Exception as e:
                self.logger.error(f"Failed to export discussions for MR {mr_iid}: {e}")
                mr_data["discussions_error"] = str(e)
            
            # Get MR approvals
            try:
                approvals = self._export_mr_approvals(project_id, mr_iid)
                mr_data["approvals"] = approvals
            except Exception as e:
                self.logger.error(f"Failed to export approvals for MR {mr_iid}: {e}")
                mr_data["approvals_error"] = str(e)
            
            # Get diff stats (summary only)
            try:
                diff_stats = self._get_diff_stats(project_id, mr_iid)
                mr_data["diff_stats"] = diff_stats
            except Exception as e:
                self.logger.error(f"Failed to get diff stats for MR {mr_iid}: {e}")
                mr_data["diff_stats_error"] = str(e)
            
            mrs_list.append(mr_data)
            
            # Log progress
            if mr_count % 20 == 0:
                self.logger.info(f"Exported {mr_count} merge requests...")
        
        # Save merge requests
        import json
        with open(output_dir / "merge_requests.json", "w", encoding="utf-8") as f:
            json.dump(mrs_list, f, indent=2, ensure_ascii=False)
        
        return {
            "total": mr_count,
            "state_counts": state_counts,
            "file": "merge_requests.json",
        }
    
    def _export_mr_discussions(self, project_id: int, mr_iid: int) -> List[Dict[str, Any]]:
        """Export discussions/threads for a merge request."""
        discussions = []
        
        for discussion in self.client.paginate(
            f"/api/v4/projects/{project_id}/merge_requests/{mr_iid}/discussions"
        ):
            notes = []
            for note in discussion.get("notes", []):
                # Skip system notes
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
                    "position": note.get("position"),  # For diff comments
                })
            
            if notes:  # Only include discussions with actual user notes
                discussions.append({
                    "id": discussion.get("id"),
                    "individual_note": discussion.get("individual_note", False),
                    "notes": notes,
                })
        
        return discussions
    
    def _export_mr_approvals(self, project_id: int, mr_iid: int) -> Dict[str, Any]:
        """Export approval information for a merge request."""
        # Get approval state
        status_code, data, _ = self.client.get(
            f"/api/v4/projects/{project_id}/merge_requests/{mr_iid}/approvals"
        )
        
        if status_code != 200 or not isinstance(data, dict):
            return {
                "available": False,
                "note": "Approvals API not available or accessible",
            }
        
        approved_by = []
        for approval in data.get("approved_by", []):
            user = approval.get("user")
            if user:
                approved_by.append(self._extract_user(user))
        
        return {
            "available": True,
            "approved": data.get("approved", False),
            "approvals_required": data.get("approvals_required", 0),
            "approvals_left": data.get("approvals_left", 0),
            "approved_by": approved_by,
        }
    
    def _get_diff_stats(self, project_id: int, mr_iid: int) -> Dict[str, Any]:
        """Get diff statistics for a merge request."""
        # Get changes (diffs)
        status_code, data, _ = self.client.get(
            f"/api/v4/projects/{project_id}/merge_requests/{mr_iid}/changes"
        )
        
        if status_code != 200 or not isinstance(data, dict):
            return {
                "available": False,
            }
        
        changes = data.get("changes", [])
        
        files_changed = len(changes)
        additions = 0
        deletions = 0
        
        for change in changes:
            diff = change.get("diff", "")
            for line in diff.splitlines():
                if line.startswith("+") and not line.startswith("+++"):
                    additions += 1
                elif line.startswith("-") and not line.startswith("---"):
                    deletions += 1
        
        return {
            "available": True,
            "files_changed": files_changed,
            "additions": additions,
            "deletions": deletions,
        }
    
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
        """Save merge requests metadata to JSON file."""
        import json
        with open(output_dir / "merge_requests_metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        self.logger.debug(f"Saved merge requests metadata to {output_dir / 'merge_requests_metadata.json'}")
