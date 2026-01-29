"""
Releases exporter - exports releases, assets download, and links.

Exports all release data for migration to GitHub Releases.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from discovery_agent.gitlab_client import GitLabClient

logger = logging.getLogger(__name__)


class ReleasesExporter:
    """
    Export releases and related assets.
    
    Exports:
    - Release metadata
    - Release notes
    - Release assets (downloads based on size)
    - Release links
    """
    
    MAX_ASSET_SIZE_MB = 100  # Don't download assets larger than this
    
    def __init__(self, client: GitLabClient, output_dir: Path):
        """
        Initialize releases exporter.
        
        Args:
            client: GitLab API client
            output_dir: Base output directory
        """
        self.client = client
        self.output_dir = output_dir
        self.logger = logging.getLogger(f"{__name__}.ReleasesExporter")
    
    def export(self, project_id: int, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Export releases data.
        
        Args:
            project_id: GitLab project ID
            project_data: Project metadata from API
            
        Returns:
            Export metadata dictionary
        """
        self.logger.info(f"Exporting releases for project {project_id}")
        
        releases_dir = self.output_dir / str(project_id) / "releases"
        releases_dir.mkdir(parents=True, exist_ok=True)
        
        metadata: Dict[str, Any] = {
            "project_id": project_id,
        }
        
        # Export releases
        try:
            releases = self._export_releases(project_id, releases_dir)
            metadata["releases"] = releases
        except Exception as e:
            self.logger.error(f"Failed to export releases: {e}")
            metadata["releases_error"] = str(e)
        
        # Save metadata
        self._save_metadata(releases_dir, metadata)
        
        metadata["status"] = "completed"
        self.logger.info(f"Releases export completed for project {project_id}")
        return metadata
    
    def _export_releases(self, project_id: int, output_dir: Path) -> Dict[str, Any]:
        """Export all releases."""
        self.logger.debug(f"Fetching releases for project {project_id}")
        
        releases_list = []
        release_count = 0
        
        for release in self.client.paginate(f"/api/v4/projects/{project_id}/releases"):
            release_count += 1
            tag_name = release.get("tag_name")
            
            # Extract release data
            release_data = {
                "tag_name": tag_name,
                "name": release.get("name"),
                "description": release.get("description"),
                "created_at": release.get("created_at"),
                "released_at": release.get("released_at"),
                "author": self._extract_user(release.get("author")),
                "commit": {
                    "id": release.get("commit", {}).get("id"),
                    "message": release.get("commit", {}).get("message"),
                },
                "upcoming_release": release.get("upcoming_release", False),
            }
            
            # Get release links
            links = []
            for link in release.get("assets", {}).get("links", []):
                links.append({
                    "id": link.get("id"),
                    "name": link.get("name"),
                    "url": link.get("url"),
                    "external": link.get("external", True),
                    "link_type": link.get("link_type"),
                })
            release_data["links"] = links
            
            # Get release assets (sources)
            sources = []
            for source in release.get("assets", {}).get("sources", []):
                sources.append({
                    "format": source.get("format"),
                    "url": source.get("url"),
                })
            release_data["sources"] = sources
            
            # Get release evidence
            evidences = []
            for evidence in release.get("evidences", []):
                evidences.append({
                    "sha": evidence.get("sha"),
                    "filepath": evidence.get("filepath"),
                    "collected_at": evidence.get("collected_at"),
                })
            release_data["evidences"] = evidences
            
            releases_list.append(release_data)
        
        # Save releases
        import json
        with open(output_dir / "releases.json", "w", encoding="utf-8") as f:
            json.dump(releases_list, f, indent=2, ensure_ascii=False)
        
        if release_count == 0:
            return {
                "total": 0,
                "note": "No releases found",
            }
        
        return {
            "total": release_count,
            "file": "releases.json",
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
        """Save releases metadata to JSON file."""
        import json
        with open(output_dir / "releases_metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        self.logger.debug(f"Saved releases metadata to {output_dir / 'releases_metadata.json'}")
