"""Preservation-related actions"""

from typing import Any, Dict
from pathlib import Path
import json
from datetime import datetime
from .base import BaseAction, ActionResult


class CommitPreservationArtifactsAction(BaseAction):
    """Commit migration metadata and preservation artifacts"""
    
    async def execute(self) -> ActionResult:
        try:
            target_repo = self.parameters["target_repo"]
            artifacts_dir = Path(self.parameters.get("artifacts_dir", "/tmp/migration_artifacts"))
            branch = self.parameters.get("branch", "main")
            
            repo = self.github_client.get_repo(target_repo)
            
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
            
            try:
                # Try to get existing file
                existing = repo.get_contents(metadata_path, ref=branch)
                repo.update_file(
                    path=metadata_path,
                    message="Update migration metadata",
                    content=metadata_content,
                    sha=existing.sha,
                    branch=branch
                )
            except:
                # Create new file
                repo.create_file(
                    path=metadata_path,
                    message="Add migration metadata",
                    content=metadata_content,
                    branch=branch
                )
            
            # Commit ID mappings
            mappings_content = json.dumps(id_mappings, indent=2)
            mappings_path = ".github/migration/id_mappings.json"
            
            try:
                existing = repo.get_contents(mappings_path, ref=branch)
                repo.update_file(
                    path=mappings_path,
                    message="Update ID mappings",
                    content=mappings_content,
                    sha=existing.sha,
                    branch=branch
                )
            except:
                repo.create_file(
                    path=mappings_path,
                    message="Add ID mappings",
                    content=mappings_content,
                    branch=branch
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
