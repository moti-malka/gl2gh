"""Preservation-related actions"""

from typing import Any, Dict
from pathlib import Path
import json
from datetime import datetime
from github import GithubException
from .base import BaseAction, ActionResult

# GitHub file size limits
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


class CommitAttachmentsAction(BaseAction):
    """Commit issue/MR attachments to GitHub repository"""
    
    async def execute(self) -> ActionResult:
        try:
            target_repo = self.parameters["target_repo"]
            export_dir = Path(self.parameters.get("export_dir", "."))
            branch = self.parameters.get("branch", "main")
            target_base_path = self.parameters.get("target_path", ".github/attachments")
            
            repo = self.github_client.get_repo(target_repo)
            
            # Track committed files
            committed_files = []
            attachment_urls = {}
            skipped_files = []
            
            # Helper function to commit attachments from a directory
            def commit_attachments_from_dir(attachments_dir: Path, subpath: str):
                if not attachments_dir.exists():
                    return
                
                for attachment_file in attachments_dir.iterdir():
                    if not attachment_file.is_file():
                        continue
                    
                    # Check file size
                    file_size = attachment_file.stat().st_size
                    if file_size > MAX_FILE_SIZE:
                        self.logger.warning(
                            f"Skipping {attachment_file.name}: "
                            f"{file_size / 1024 / 1024:.1f} MB exceeds GitHub limit (100 MB)"
                        )
                        skipped_files.append(str(attachment_file))
                        continue
                    
                    file_path = f"{target_base_path}/{subpath}/{attachment_file.name}"
                    
                    with open(attachment_file, 'rb') as f:
                        content = f.read()
                    
                    try:
                        # Try to get existing file
                        existing = repo.get_contents(file_path, ref=branch)
                        repo.update_file(
                            path=file_path,
                            message=f"Update attachment: {attachment_file.name}",
                            content=content,
                            sha=existing.sha,
                            branch=branch
                        )
                    except GithubException as e:
                        if e.status == 404:
                            # File doesn't exist, create new file
                            try:
                                repo.create_file(
                                    path=file_path,
                                    message=f"Add attachment: {attachment_file.name}",
                                    content=content,
                                    branch=branch
                                )
                            except GithubException as create_error:
                                self.logger.error(f"Failed to create {file_path}: {create_error}")
                                skipped_files.append(str(attachment_file))
                                continue
                        else:
                            self.logger.error(f"Failed to process {file_path}: {e}")
                            skipped_files.append(str(attachment_file))
                            continue
                    
                    committed_files.append(file_path)
                    # Generate GitHub URL for the file
                    attachment_urls[attachment_file.name] = f"https://github.com/{target_repo}/blob/{branch}/{file_path}"
            
            # Process issue attachments
            issues_attachments_dir = export_dir / "issues" / "attachments"
            commit_attachments_from_dir(issues_attachments_dir, "issues")
            
            # Process MR attachments
            mr_attachments_dir = export_dir / "merge_requests" / "attachments"
            commit_attachments_from_dir(mr_attachments_dir, "merge_requests")
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "committed_files": committed_files,
                    "attachment_urls": attachment_urls,
                    "skipped_files": skipped_files,
                    "count": len(committed_files),
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
            except GithubException as e:
                if e.status == 404:
                    # File doesn't exist, create new file
                    repo.create_file(
                        path=metadata_path,
                        message="Add migration metadata",
                        content=metadata_content,
                        branch=branch
                    )
                else:
                    raise
            
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
            except GithubException as e:
                if e.status == 404:
                    # File doesn't exist, create new file
                    repo.create_file(
                        path=mappings_path,
                        message="Add ID mappings",
                        content=mappings_content,
                        branch=branch
                    )
                else:
                    raise
            
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
