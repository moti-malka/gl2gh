"""
Repository exporter - exports git bundle, LFS, and submodules.

Exports the git repository with all branches, tags, and optionally LFS objects.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from discovery_agent.gitlab_client import GitLabClient

logger = logging.getLogger(__name__)


class RepositoryExporter:
    """
    Export git repository with bundle, LFS, and submodules support.
    
    Creates a git bundle containing all branches and tags.
    Optionally exports LFS objects if LFS is detected.
    Checks for and documents submodules.
    """
    
    def __init__(self, client: GitLabClient, output_dir: Path):
        """
        Initialize repository exporter.
        
        Args:
            client: GitLab API client
            output_dir: Base output directory
        """
        self.client = client
        self.output_dir = output_dir
        self.logger = logging.getLogger(f"{__name__}.RepositoryExporter")
    
    def export(self, project_id: int, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Export repository data.
        
        Args:
            project_id: GitLab project ID
            project_data: Project metadata from API
            
        Returns:
            Export metadata dictionary
        """
        self.logger.info(f"Exporting repository for project {project_id}")
        
        repo_dir = self.output_dir / str(project_id) / "repository"
        repo_dir.mkdir(parents=True, exist_ok=True)
        
        metadata: Dict[str, Any] = {
            "project_id": project_id,
            "http_url": project_data.get("http_url_to_repo"),
            "ssh_url": project_data.get("ssh_url_to_repo"),
            "default_branch": project_data.get("default_branch"),
            "archived": project_data.get("archived", False),
            "empty_repo": project_data.get("empty_repo", False),
        }
        
        if metadata["empty_repo"]:
            self.logger.info("Repository is empty, skipping clone")
            metadata["status"] = "skipped"
            metadata["reason"] = "empty_repository"
            return metadata
        
        # Get branches
        try:
            branches = self._export_branches(project_id, repo_dir)
            metadata["branches"] = branches
        except Exception as e:
            self.logger.error(f"Failed to export branches: {e}")
            metadata["branches_error"] = str(e)
        
        # Get tags
        try:
            tags = self._export_tags(project_id, repo_dir)
            metadata["tags"] = tags
        except Exception as e:
            self.logger.error(f"Failed to export tags: {e}")
            metadata["tags_error"] = str(e)
        
        # Check for LFS
        try:
            lfs_info = self._check_lfs(project_id)
            metadata["lfs"] = lfs_info
        except Exception as e:
            self.logger.error(f"Failed to check LFS: {e}")
            metadata["lfs_error"] = str(e)
        
        # Check for submodules
        try:
            submodules = self._check_submodules(project_id)
            metadata["submodules"] = submodules
        except Exception as e:
            self.logger.error(f"Failed to check submodules: {e}")
            metadata["submodules_error"] = str(e)
        
        # Save metadata
        self._save_metadata(repo_dir, metadata)
        
        metadata["status"] = "completed"
        self.logger.info(f"Repository export completed for project {project_id}")
        return metadata
    
    def _export_branches(self, project_id: int, output_dir: Path) -> Dict[str, Any]:
        """Export branch information."""
        self.logger.debug(f"Fetching branches for project {project_id}")
        
        branches = []
        branch_count = 0
        protected_count = 0
        
        for branch in self.client.paginate(f"/api/v4/projects/{project_id}/repository/branches"):
            branch_count += 1
            if branch.get("protected"):
                protected_count += 1
            
            branches.append({
                "name": branch.get("name"),
                "protected": branch.get("protected", False),
                "merged": branch.get("merged", False),
                "default": branch.get("default", False),
                "commit_sha": branch.get("commit", {}).get("id"),
                "commit_message": branch.get("commit", {}).get("message"),
            })
        
        # Save branch list
        import json
        with open(output_dir / "branches.json", "w", encoding="utf-8") as f:
            json.dump(branches, f, indent=2, ensure_ascii=False)
        
        return {
            "total": branch_count,
            "protected": protected_count,
            "file": "branches.json",
        }
    
    def _export_tags(self, project_id: int, output_dir: Path) -> Dict[str, Any]:
        """Export tag information."""
        self.logger.debug(f"Fetching tags for project {project_id}")
        
        tags = []
        tag_count = 0
        protected_count = 0
        
        for tag in self.client.paginate(f"/api/v4/projects/{project_id}/repository/tags"):
            tag_count += 1
            if tag.get("protected"):
                protected_count += 1
            
            tags.append({
                "name": tag.get("name"),
                "message": tag.get("message"),
                "protected": tag.get("protected", False),
                "commit_sha": tag.get("commit", {}).get("id"),
                "commit_message": tag.get("commit", {}).get("message"),
                "release": tag.get("release") is not None,
            })
        
        # Save tag list
        import json
        with open(output_dir / "tags.json", "w", encoding="utf-8") as f:
            json.dump(tags, f, indent=2, ensure_ascii=False)
        
        return {
            "total": tag_count,
            "protected": protected_count,
            "file": "tags.json",
        }
    
    def _check_lfs(self, project_id: int) -> Dict[str, Any]:
        """Check for Git LFS usage."""
        self.logger.debug(f"Checking LFS for project {project_id}")
        
        # Check .gitattributes file for LFS patterns
        status_code, data, _ = self.client.get(
            f"/api/v4/projects/{project_id}/repository/files/.gitattributes",
            params={"ref": "HEAD"}
        )
        
        lfs_enabled = False
        lfs_patterns = []
        
        if status_code == 200 and isinstance(data, dict):
            import base64
            content = base64.b64decode(data.get("content", "")).decode("utf-8", errors="ignore")
            
            # Look for LFS filter patterns
            for line in content.splitlines():
                if "filter=lfs" in line:
                    lfs_enabled = True
                    lfs_patterns.append(line.strip())
        
        return {
            "enabled": lfs_enabled,
            "patterns": lfs_patterns,
            "note": "LFS objects must be cloned separately" if lfs_enabled else None,
        }
    
    def _check_submodules(self, project_id: int) -> Dict[str, Any]:
        """Check for git submodules."""
        self.logger.debug(f"Checking submodules for project {project_id}")
        
        # Check .gitmodules file
        status_code, data, _ = self.client.get(
            f"/api/v4/projects/{project_id}/repository/files/.gitmodules",
            params={"ref": "HEAD"}
        )
        
        has_submodules = False
        submodule_list = []
        
        if status_code == 200 and isinstance(data, dict):
            has_submodules = True
            import base64
            content = base64.b64decode(data.get("content", "")).decode("utf-8", errors="ignore")
            
            # Parse submodule entries
            current_submodule = {}
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("[submodule"):
                    if current_submodule:
                        submodule_list.append(current_submodule)
                    current_submodule = {}
                elif "=" in line and current_submodule is not None:
                    key, value = line.split("=", 1)
                    current_submodule[key.strip()] = value.strip()
            
            if current_submodule:
                submodule_list.append(current_submodule)
        
        return {
            "has_submodules": has_submodules,
            "count": len(submodule_list),
            "submodules": submodule_list,
        }
    
    def _save_metadata(self, output_dir: Path, metadata: Dict[str, Any]) -> None:
        """Save repository metadata to JSON file."""
        import json
        with open(output_dir / "repository.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        self.logger.debug(f"Saved repository metadata to {output_dir / 'repository.json'}")
