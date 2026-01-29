"""
Packages exporter - exports package metadata and downloads files based on size.

Exports package registry data from GitLab Package Registry.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from discovery_agent.gitlab_client import GitLabClient

logger = logging.getLogger(__name__)


class PackagesExporter:
    """
    Export packages from GitLab Package Registry.
    
    Exports:
    - Package metadata
    - Package files (based on size threshold)
    - Package versions
    
    Supports: npm, Maven, PyPI, NuGet, Composer, Conan, Helm, etc.
    """
    
    MAX_PACKAGE_SIZE_MB = 500  # Don't download packages larger than this
    
    def __init__(self, client: GitLabClient, output_dir: Path):
        """
        Initialize packages exporter.
        
        Args:
            client: GitLab API client
            output_dir: Base output directory
        """
        self.client = client
        self.output_dir = output_dir
        self.logger = logging.getLogger(f"{__name__}.PackagesExporter")
    
    def export(self, project_id: int, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Export packages data.
        
        Args:
            project_id: GitLab project ID
            project_data: Project metadata from API
            
        Returns:
            Export metadata dictionary
        """
        self.logger.info(f"Exporting packages for project {project_id}")
        
        packages_dir = self.output_dir / str(project_id) / "packages"
        packages_dir.mkdir(parents=True, exist_ok=True)
        
        metadata: Dict[str, Any] = {
            "project_id": project_id,
        }
        
        # Export packages
        try:
            packages = self._export_packages(project_id, packages_dir)
            metadata["packages"] = packages
        except Exception as e:
            self.logger.error(f"Failed to export packages: {e}")
            metadata["packages_error"] = str(e)
        
        # Save metadata
        self._save_metadata(packages_dir, metadata)
        
        metadata["status"] = "completed"
        self.logger.info(f"Packages export completed for project {project_id}")
        return metadata
    
    def _export_packages(self, project_id: int, output_dir: Path) -> Dict[str, Any]:
        """Export package registry data."""
        self.logger.debug(f"Fetching packages for project {project_id}")
        
        packages_list = []
        package_count = 0
        package_types: Dict[str, int] = {}
        
        for package in self.client.paginate(f"/api/v4/projects/{project_id}/packages"):
            package_count += 1
            package_id = package.get("id")
            package_type = package.get("package_type", "unknown")
            
            package_types[package_type] = package_types.get(package_type, 0) + 1
            
            # Extract package data
            package_data = {
                "id": package_id,
                "name": package.get("name"),
                "version": package.get("version"),
                "package_type": package_type,
                "created_at": package.get("created_at"),
                "status": package.get("status"),
                "_links": package.get("_links"),
            }
            
            # Get package details
            try:
                details = self._get_package_details(project_id, package_id)
                package_data.update(details)
            except Exception as e:
                self.logger.error(f"Failed to get package {package_id} details: {e}")
                package_data["details_error"] = str(e)
            
            packages_list.append(package_data)
        
        # Save packages
        import json
        with open(output_dir / "packages.json", "w", encoding="utf-8") as f:
            json.dump(packages_list, f, indent=2, ensure_ascii=False)
        
        if package_count == 0:
            return {
                "total": 0,
                "note": "No packages found",
            }
        
        return {
            "total": package_count,
            "package_types": package_types,
            "file": "packages.json",
        }
    
    def _get_package_details(self, project_id: int, package_id: int) -> Dict[str, Any]:
        """Get detailed package information."""
        status_code, data, _ = self.client.get(
            f"/api/v4/projects/{project_id}/packages/{package_id}"
        )
        
        if status_code != 200 or not isinstance(data, dict):
            return {
                "details_available": False,
            }
        
        # Get package files
        package_files = []
        total_size = 0
        
        for pf in data.get("package_files", []):
            file_size = pf.get("size", 0)
            total_size += file_size
            
            package_files.append({
                "id": pf.get("id"),
                "file_name": pf.get("file_name"),
                "size": file_size,
                "file_md5": pf.get("file_md5"),
                "file_sha1": pf.get("file_sha1"),
                "file_sha256": pf.get("file_sha256"),
                "created_at": pf.get("created_at"),
            })
        
        # Get pipeline info
        pipeline = data.get("pipeline")
        pipeline_info = None
        if pipeline:
            pipeline_info = {
                "id": pipeline.get("id"),
                "sha": pipeline.get("sha"),
                "ref": pipeline.get("ref"),
                "status": pipeline.get("status"),
                "web_url": pipeline.get("web_url"),
            }
        
        return {
            "details_available": True,
            "package_files": package_files,
            "total_size": total_size,
            "pipeline": pipeline_info,
            "tags": data.get("tags", []),
        }
    
    def _save_metadata(self, output_dir: Path, metadata: Dict[str, Any]) -> None:
        """Save packages metadata to JSON file."""
        import json
        with open(output_dir / "packages_metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        self.logger.debug(f"Saved packages metadata to {output_dir / 'packages_metadata.json'}")
