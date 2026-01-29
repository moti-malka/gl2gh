"""
CI/CD exporter - exports .gitlab-ci.yml, includes, variables, environments, schedules, and pipeline history.

Exports all CI/CD configuration and pipeline data for migration to GitHub Actions.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any, Dict, List

from discovery_agent.gitlab_client import GitLabClient

logger = logging.getLogger(__name__)


class CICDExporter:
    """
    Export CI/CD configuration and pipeline data.
    
    Exports:
    - .gitlab-ci.yml configuration file
    - Pipeline schedules
    - CI/CD variables (metadata only, not secret values)
    - Environments
    - Recent pipeline runs
    - Job artifacts metadata
    """
    
    def __init__(self, client: GitLabClient, output_dir: Path):
        """
        Initialize CI/CD exporter.
        
        Args:
            client: GitLab API client
            output_dir: Base output directory
        """
        self.client = client
        self.output_dir = output_dir
        self.logger = logging.getLogger(f"{__name__}.CICDExporter")
    
    def export(self, project_id: int, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Export CI/CD data.
        
        Args:
            project_id: GitLab project ID
            project_data: Project metadata from API
            
        Returns:
            Export metadata dictionary
        """
        self.logger.info(f"Exporting CI/CD for project {project_id}")
        
        cicd_dir = self.output_dir / str(project_id) / "cicd"
        cicd_dir.mkdir(parents=True, exist_ok=True)
        
        metadata: Dict[str, Any] = {
            "project_id": project_id,
        }
        
        # Export .gitlab-ci.yml
        try:
            ci_config = self._export_ci_config(project_id, cicd_dir)
            metadata["ci_config"] = ci_config
        except Exception as e:
            self.logger.error(f"Failed to export CI config: {e}")
            metadata["ci_config_error"] = str(e)
        
        # Export variables
        try:
            variables = self._export_variables(project_id, cicd_dir)
            metadata["variables"] = variables
        except Exception as e:
            self.logger.error(f"Failed to export variables: {e}")
            metadata["variables_error"] = str(e)
        
        # Export environments
        try:
            environments = self._export_environments(project_id, cicd_dir)
            metadata["environments"] = environments
        except Exception as e:
            self.logger.error(f"Failed to export environments: {e}")
            metadata["environments_error"] = str(e)
        
        # Export pipeline schedules
        try:
            schedules = self._export_schedules(project_id, cicd_dir)
            metadata["schedules"] = schedules
        except Exception as e:
            self.logger.error(f"Failed to export schedules: {e}")
            metadata["schedules_error"] = str(e)
        
        # Export pipeline history
        try:
            pipelines = self._export_pipeline_history(project_id, cicd_dir)
            metadata["pipelines"] = pipelines
        except Exception as e:
            self.logger.error(f"Failed to export pipeline history: {e}")
            metadata["pipelines_error"] = str(e)
        
        # Save metadata
        self._save_metadata(cicd_dir, metadata)
        
        metadata["status"] = "completed"
        self.logger.info(f"CI/CD export completed for project {project_id}")
        return metadata
    
    def _export_ci_config(self, project_id: int, output_dir: Path) -> Dict[str, Any]:
        """Export .gitlab-ci.yml configuration file."""
        self.logger.debug(f"Fetching CI config for project {project_id}")
        
        # Try to get .gitlab-ci.yml from repository
        status_code, data, _ = self.client.get(
            f"/api/v4/projects/{project_id}/repository/files/.gitlab-ci.yml",
            params={"ref": "HEAD"}
        )
        
        if status_code == 200 and isinstance(data, dict):
            content = base64.b64decode(data.get("content", "")).decode("utf-8", errors="ignore")
            
            # Save the file
            with open(output_dir / ".gitlab-ci.yml", "w", encoding="utf-8") as f:
                f.write(content)
            
            # Check for includes
            includes = []
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("include:") or "include:" in line:
                    includes.append(line)
            
            return {
                "found": True,
                "file": ".gitlab-ci.yml",
                "size_bytes": len(content),
                "has_includes": len(includes) > 0,
                "include_lines": includes,
            }
        elif status_code == 404:
            self.logger.info("No .gitlab-ci.yml found")
            return {
                "found": False,
                "reason": "file_not_found",
            }
        else:
            self.logger.warning(f"Failed to fetch .gitlab-ci.yml: {status_code}")
            return {
                "found": False,
                "reason": "api_error",
                "status_code": status_code,
            }
    
    def _export_variables(self, project_id: int, output_dir: Path) -> Dict[str, Any]:
        """Export CI/CD variables (metadata only, not values)."""
        self.logger.debug(f"Fetching CI/CD variables for project {project_id}")
        
        variables = []
        variable_count = 0
        protected_count = 0
        masked_count = 0
        
        for var in self.client.paginate(f"/api/v4/projects/{project_id}/variables"):
            variable_count += 1
            if var.get("protected"):
                protected_count += 1
            if var.get("masked"):
                masked_count += 1
            
            # Store metadata only, never the actual value
            variables.append({
                "key": var.get("key"),
                "variable_type": var.get("variable_type", "env_var"),
                "protected": var.get("protected", False),
                "masked": var.get("masked", False),
                "environment_scope": var.get("environment_scope", "*"),
                "note": "Value not exported for security",
            })
        
        # Save variables
        import json
        with open(output_dir / "variables.json", "w", encoding="utf-8") as f:
            json.dump(variables, f, indent=2, ensure_ascii=False)
        
        return {
            "total": variable_count,
            "protected": protected_count,
            "masked": masked_count,
            "file": "variables.json",
        }
    
    def _export_environments(self, project_id: int, output_dir: Path) -> Dict[str, Any]:
        """Export environment configurations."""
        self.logger.debug(f"Fetching environments for project {project_id}")
        
        environments = []
        env_count = 0
        
        for env in self.client.paginate(f"/api/v4/projects/{project_id}/environments"):
            env_count += 1
            environments.append({
                "id": env.get("id"),
                "name": env.get("name"),
                "state": env.get("state"),
                "external_url": env.get("external_url"),
                "created_at": env.get("created_at"),
                "updated_at": env.get("updated_at"),
            })
        
        # Save environments
        import json
        with open(output_dir / "environments.json", "w", encoding="utf-8") as f:
            json.dump(environments, f, indent=2, ensure_ascii=False)
        
        return {
            "total": env_count,
            "file": "environments.json",
        }
    
    def _export_schedules(self, project_id: int, output_dir: Path) -> Dict[str, Any]:
        """Export pipeline schedules."""
        self.logger.debug(f"Fetching pipeline schedules for project {project_id}")
        
        schedules = []
        schedule_count = 0
        active_count = 0
        
        for schedule in self.client.paginate(f"/api/v4/projects/{project_id}/pipeline_schedules"):
            schedule_count += 1
            if schedule.get("active"):
                active_count += 1
            
            schedules.append({
                "id": schedule.get("id"),
                "description": schedule.get("description"),
                "ref": schedule.get("ref"),
                "cron": schedule.get("cron"),
                "cron_timezone": schedule.get("cron_timezone"),
                "active": schedule.get("active", False),
                "created_at": schedule.get("created_at"),
                "updated_at": schedule.get("updated_at"),
                "owner": {
                    "username": schedule.get("owner", {}).get("username"),
                    "name": schedule.get("owner", {}).get("name"),
                },
            })
        
        # Save schedules
        import json
        with open(output_dir / "schedules.json", "w", encoding="utf-8") as f:
            json.dump(schedules, f, indent=2, ensure_ascii=False)
        
        return {
            "total": schedule_count,
            "active": active_count,
            "file": "schedules.json",
        }
    
    def _export_pipeline_history(self, project_id: int, output_dir: Path, max_pipelines: int = 100) -> Dict[str, Any]:
        """Export recent pipeline runs."""
        self.logger.debug(f"Fetching pipeline history for project {project_id}")
        
        pipelines = []
        pipeline_count = 0
        status_counts: Dict[str, int] = {}
        
        # Fetch recent pipelines
        for pipeline in self.client.paginate(
            f"/api/v4/projects/{project_id}/pipelines",
            params={"order_by": "id", "sort": "desc"},
            max_items=max_pipelines
        ):
            pipeline_count += 1
            status = pipeline.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            
            pipelines.append({
                "id": pipeline.get("id"),
                "iid": pipeline.get("iid"),
                "ref": pipeline.get("ref"),
                "sha": pipeline.get("sha"),
                "status": status,
                "source": pipeline.get("source"),
                "created_at": pipeline.get("created_at"),
                "updated_at": pipeline.get("updated_at"),
                "web_url": pipeline.get("web_url"),
            })
        
        # Save pipeline history
        import json
        with open(output_dir / "pipelines.json", "w", encoding="utf-8") as f:
            json.dump(pipelines, f, indent=2, ensure_ascii=False)
        
        return {
            "total": pipeline_count,
            "status_counts": status_counts,
            "file": "pipelines.json",
            "note": f"Limited to {max_pipelines} most recent pipelines",
        }
    
    def _save_metadata(self, output_dir: Path, metadata: Dict[str, Any]) -> None:
        """Save CI/CD metadata to JSON file."""
        import json
        with open(output_dir / "cicd.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        self.logger.debug(f"Saved CI/CD metadata to {output_dir / 'cicd.json'}")
