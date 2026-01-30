"""Preservation-related actions"""

from typing import Any, Dict
from pathlib import Path
import json
from datetime import datetime
from .base import BaseAction, ActionResult
import httpx


class CommitPreservationArtifactsAction(BaseAction):
    """Commit migration metadata and preservation artifacts"""
    
    async def execute(self) -> ActionResult:
        try:
            target_repo = self.parameters["target_repo"]
            artifacts_dir = Path(self.parameters.get("artifacts_dir", "/tmp/migration_artifacts"))
            branch = self.parameters.get("branch", "main")
            
            # Prepare migration metadata
            id_mappings = self.context.get("id_mappings", {})
            migration_timestamp = datetime.utcnow().isoformat()
            
            metadata = {
                "migration_date": migration_timestamp,
                "source": "GitLab",
                "tool": "gl2gh",
                "version": "1.0.0",
                "id_mappings": id_mappings
            }
            
            # Commit metadata file
            metadata_content = json.dumps(metadata, indent=2)
            metadata_path = ".github/migration/metadata.json"
            
            # Try to get existing file SHA
            sha = None
            try:
                response = await self.github_client._request(
                    'GET',
                    f"/repos/{target_repo}/contents/{metadata_path}",
                    params={"ref": branch}
                )
                file_data = response.json()
                sha = file_data["sha"]
            except httpx.HTTPStatusError:
                pass  # File doesn't exist
            
            await self.github_client.create_or_update_file(
                repo=target_repo,
                path=metadata_path,
                content=metadata_content,
                message="Add migration metadata" if not sha else "Update migration metadata",
                branch=branch,
                sha=sha
            )
            
            # Commit ID mappings
            mappings_content = json.dumps(id_mappings, indent=2)
            mappings_path = ".github/migration/id_mappings.json"
            
            # Try to get existing file SHA
            sha = None
            try:
                response = await self.github_client._request(
                    'GET',
                    f"/repos/{target_repo}/contents/{mappings_path}",
                    params={"ref": branch}
                )
                file_data = response.json()
                sha = file_data["sha"]
            except httpx.HTTPStatusError:
                pass  # File doesn't exist
            
            await self.github_client.create_or_update_file(
                repo=target_repo,
                path=mappings_path,
                content=mappings_content,
                message="Add ID mappings" if not sha else "Update ID mappings",
                branch=branch,
                sha=sha
            )
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "metadata_committed": True,
                    "metadata_path": metadata_path,
                    "mappings_path": mappings_path,
                    "target_repo": target_repo
                }
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=str(e)
            )
