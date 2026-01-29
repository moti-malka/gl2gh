"""
Wiki exporter - clones and exports wiki repository.

Exports the project wiki as a git repository.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from discovery_agent.gitlab_client import GitLabClient

logger = logging.getLogger(__name__)


class WikiExporter:
    """
    Export project wiki.
    
    Exports:
    - Wiki pages and history
    - Wiki attachments
    - Wiki metadata
    
    Note: Wikis in GitLab are separate git repositories.
    """
    
    def __init__(self, client: GitLabClient, output_dir: Path):
        """
        Initialize wiki exporter.
        
        Args:
            client: GitLab API client
            output_dir: Base output directory
        """
        self.client = client
        self.output_dir = output_dir
        self.logger = logging.getLogger(f"{__name__}.WikiExporter")
    
    def export(self, project_id: int, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Export wiki data.
        
        Args:
            project_id: GitLab project ID
            project_data: Project metadata from API
            
        Returns:
            Export metadata dictionary
        """
        self.logger.info(f"Exporting wiki for project {project_id}")
        
        wiki_dir = self.output_dir / str(project_id) / "wiki"
        wiki_dir.mkdir(parents=True, exist_ok=True)
        
        metadata: Dict[str, Any] = {
            "project_id": project_id,
        }
        
        # Check if wiki is enabled
        if not project_data.get("wiki_enabled", False):
            self.logger.info(f"Wiki not enabled for project {project_id}")
            metadata["status"] = "skipped"
            metadata["reason"] = "wiki_not_enabled"
            return metadata
        
        # Export wiki pages
        try:
            wiki_pages = self._export_wiki_pages(project_id, wiki_dir)
            metadata["wiki_pages"] = wiki_pages
        except Exception as e:
            self.logger.error(f"Failed to export wiki pages: {e}")
            metadata["wiki_pages_error"] = str(e)
        
        # Save metadata
        self._save_metadata(wiki_dir, metadata)
        
        metadata["status"] = "completed"
        self.logger.info(f"Wiki export completed for project {project_id}")
        return metadata
    
    def _export_wiki_pages(self, project_id: int, output_dir: Path) -> Dict[str, Any]:
        """Export wiki pages."""
        self.logger.debug(f"Fetching wiki pages for project {project_id}")
        
        pages = []
        page_count = 0
        
        # Get list of wiki pages
        for page in self.client.paginate(f"/api/v4/projects/{project_id}/wikis"):
            page_count += 1
            slug = page.get("slug")
            
            page_data = {
                "slug": slug,
                "title": page.get("title"),
                "format": page.get("format", "markdown"),
            }
            
            # Get full page content
            try:
                page_detail = self._get_wiki_page(project_id, slug)
                page_data.update(page_detail)
            except Exception as e:
                self.logger.error(f"Failed to get wiki page {slug}: {e}")
                page_data["error"] = str(e)
            
            pages.append(page_data)
        
        # Save pages metadata and content
        import json
        with open(output_dir / "wiki_pages.json", "w", encoding="utf-8") as f:
            json.dump(pages, f, indent=2, ensure_ascii=False)
        
        # Save individual page content
        pages_dir = output_dir / "pages"
        pages_dir.mkdir(exist_ok=True)
        
        for page in pages:
            if "content" in page:
                slug = page["slug"]
                format_ext = page.get("format", "markdown")
                if format_ext == "markdown":
                    ext = "md"
                elif format_ext == "rdoc":
                    ext = "rdoc"
                elif format_ext == "asciidoc":
                    ext = "adoc"
                elif format_ext == "org":
                    ext = "org"
                else:
                    ext = "txt"
                
                with open(pages_dir / f"{slug}.{ext}", "w", encoding="utf-8") as f:
                    f.write(page["content"])
        
        if page_count == 0:
            return {
                "total": 0,
                "note": "No wiki pages found",
            }
        
        return {
            "total": page_count,
            "file": "wiki_pages.json",
            "pages_dir": "pages/",
        }
    
    def _get_wiki_page(self, project_id: int, slug: str) -> Dict[str, Any]:
        """Get detailed wiki page content."""
        status_code, data, _ = self.client.get(
            f"/api/v4/projects/{project_id}/wikis/{slug}"
        )
        
        if status_code != 200 or not isinstance(data, dict):
            raise Exception(f"Failed to get wiki page: status {status_code}")
        
        return {
            "content": data.get("content"),
            "encoding": data.get("encoding", "utf-8"),
        }
    
    def _save_metadata(self, output_dir: Path, metadata: Dict[str, Any]) -> None:
        """Save wiki metadata to JSON file."""
        import json
        with open(output_dir / "wiki.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        self.logger.debug(f"Saved wiki metadata to {output_dir / 'wiki.json'}")
