"""Repository-related actions"""

import json
from typing import Any, Dict
from pathlib import Path
import subprocess
import shutil
import tempfile
from .base import BaseAction, ActionResult
from github import GithubException


class CreateRepositoryAction(BaseAction):
    """Create GitHub repository"""
    
    async def execute(self) -> ActionResult:
        try:
            org_or_user = self.parameters.get("org") or self.parameters.get("owner")
            repo_name = self.parameters["name"]
            
            # Get organization or user
            try:
                org = self.github_client.get_organization(org_or_user)
                repo = org.create_repo(
                    name=repo_name,
                    description=self.parameters.get("description", ""),
                    homepage=self.parameters.get("homepage", ""),
                    private=self.parameters.get("private", True),
                    has_issues=self.parameters.get("has_issues", True),
                    has_projects=self.parameters.get("has_projects", True),
                    has_wiki=self.parameters.get("has_wiki", True),
                    auto_init=self.parameters.get("auto_init", False),
                )
            except GithubException as e:
                # If organization not found (404), try as user
                if e.status == 404:
                    user = self.github_client.get_user(org_or_user)
                    repo = user.create_repo(
                        name=repo_name,
                        description=self.parameters.get("description", ""),
                        homepage=self.parameters.get("homepage", ""),
                        private=self.parameters.get("private", True),
                        has_issues=self.parameters.get("has_issues", True),
                        has_projects=self.parameters.get("has_projects", True),
                        has_wiki=self.parameters.get("has_wiki", True),
                        auto_init=self.parameters.get("auto_init", False),
                    )
                else:
                    raise
            
            # Set topics if provided
            topics = self.parameters.get("topics", [])
            if topics:
                repo.replace_topics(topics)
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "repo_full_name": repo.full_name,
                    "repo_url": repo.html_url,
                    "repo_id": repo.id
                }
            )
        except GithubException as e:
            # Check if repo already exists
            if e.status == 422:
                self.logger.warning(f"Repository {org_or_user}/{repo_name} already exists")
                return ActionResult(
                    success=True,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={"repo_full_name": f"{org_or_user}/{repo_name}", "exists": True}
                )
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=f"Failed to create repository: {str(e)}"
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=str(e)
            )


class PushCodeAction(BaseAction):
    """Push git bundle to GitHub repository"""
    
    async def execute(self) -> ActionResult:
        try:
            bundle_path = Path(self.parameters["bundle_path"])
            target_repo = self.parameters["target_repo"]
            
            if not bundle_path.exists():
                raise FileNotFoundError(f"Bundle file not found: {bundle_path}")
            
            # Get repository
            repo = self.github_client.get_repo(target_repo)
            clone_url = repo.clone_url
            
            # Create temp directory for unpacking using tempfile for security
            temp_dir = Path(tempfile.mkdtemp(prefix="gl2gh_repo_"))
            
            try:
                # Clone from bundle
                subprocess.run(
                    ["git", "clone", str(bundle_path), str(temp_dir)],
                    check=True,
                    capture_output=True,
                    text=True
                )
                
                # Add GitHub remote with token (token will be redacted in error messages)
                token = self.context.get("github_token")
                auth_url = clone_url.replace("https://", f"https://x-access-token:{token}@")
                
                subprocess.run(
                    ["git", "remote", "add", "github", auth_url],
                    cwd=temp_dir,
                    check=True,
                    capture_output=True,
                    text=True
                )
                
                # Push all branches and tags
                subprocess.run(
                    ["git", "push", "github", "--all"],
                    cwd=temp_dir,
                    check=True,
                    capture_output=True,
                    text=True
                )
                
                subprocess.run(
                    ["git", "push", "github", "--tags"],
                    cwd=temp_dir,
                    check=True,
                    capture_output=True,
                    text=True
                )
                
                return ActionResult(
                    success=True,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={"pushed": True, "target_repo": target_repo}
                )
            finally:
                # Cleanup temp directory
                if temp_dir.exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    
        except subprocess.CalledProcessError as e:
            # Redact token from error messages
            error_msg = str(e.stderr if e.stderr else str(e))
            token = self.context.get("github_token", "")
            if token:
                error_msg = error_msg.replace(token, "***REDACTED***")
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=f"Git operation failed: {error_msg}"
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=str(e)
            )


class PushLFSAction(BaseAction):
    """Configure and push Git LFS objects"""
    
    async def execute(self) -> ActionResult:
        try:
            lfs_objects_path = Path(self.parameters["lfs_objects_path"])
            target_repo = self.parameters["target_repo"]
            
            # Check if LFS objects exist
            if not lfs_objects_path.exists():
                return ActionResult(
                    success=True,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={"skipped": True, "reason": "No LFS objects found"}
                )
            
            # Check if manifest exists
            manifest_path = lfs_objects_path / "manifest.json"
            if not manifest_path.exists():
                return ActionResult(
                    success=True,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={"skipped": True, "reason": "No LFS manifest found"}
                )
            
            # Read manifest
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            
            lfs_count = manifest.get("total_count", 0)
            if lfs_count == 0:
                return ActionResult(
                    success=True,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={"skipped": True, "reason": "No LFS objects to push"}
                )
            
            self.logger.info(f"Pushing {lfs_count} LFS objects to {target_repo}")
            
            # Get repository
            repo = self.github_client.get_repo(target_repo)
            clone_url = repo.clone_url
            
            # Create temp directory for LFS push using tempfile for security
            temp_dir = Path(tempfile.mkdtemp(prefix="gl2gh_lfs_"))
            
            try:
                # Clone repository (we need a full clone for LFS, not bare)
                token = self.context.get("github_token")
                auth_url = clone_url.replace("https://", f"https://x-access-token:{token}@")
                
                subprocess.run(
                    ["git", "clone", auth_url, str(temp_dir)],
                    check=True,
                    capture_output=True,
                    text=True
                )
                
                # Install Git LFS in the repository
                subprocess.run(
                    ["git", "lfs", "install"],
                    cwd=temp_dir,
                    check=True,
                    capture_output=True,
                    text=True
                )
                
                # Copy LFS objects to the cloned repository
                lfs_storage_src = lfs_objects_path / "objects"
                if lfs_storage_src.exists():
                    lfs_storage_dst = temp_dir / ".git" / "lfs" / "objects"
                    lfs_storage_dst.mkdir(parents=True, exist_ok=True)
                    
                    # Copy all LFS objects
                    import shutil
                    for item in lfs_storage_src.iterdir():
                        if item.is_dir():
                            dst_path = lfs_storage_dst / item.name
                            if dst_path.exists():
                                shutil.rmtree(dst_path)
                            shutil.copytree(item, dst_path)
                        else:
                            shutil.copy2(item, lfs_storage_dst / item.name)
                
                # Push all LFS objects to GitHub
                self.logger.info("Pushing LFS objects to GitHub...")
                result = subprocess.run(
                    ["git", "lfs", "push", "--all", "origin"],
                    cwd=temp_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=600  # 10 minutes for large LFS files
                )
                
                self.logger.info(f"Successfully pushed {lfs_count} LFS objects")
                
                return ActionResult(
                    success=True,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={
                        "lfs_configured": True,
                        "target_repo": target_repo,
                        "objects_pushed": lfs_count,
                        "total_size": manifest.get("total_size", 0)
                    }
                )
            finally:
                # Cleanup temp directory
                if temp_dir.exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    
        except subprocess.TimeoutExpired as e:
            error_msg = f"LFS push timed out: {e.cmd[0] if e.cmd else 'unknown'}"
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=error_msg
            )
        except subprocess.CalledProcessError as e:
            # Redact token from error messages
            error_msg = str(e.stderr if e.stderr else str(e))
            token = self.context.get("github_token", "")
            if token:
                error_msg = error_msg.replace(token, "***REDACTED***")
            
            # Check for common LFS errors
            if "quota" in error_msg.lower() or "storage" in error_msg.lower():
                error_msg = f"LFS quota/storage error: {error_msg}"
            elif "authentication" in error_msg.lower():
                error_msg = f"LFS authentication error: {error_msg}"
            else:
                error_msg = f"LFS push failed: {error_msg}"
            
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=error_msg
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=str(e)
            )


class ConfigureRepositoryAction(BaseAction):
    """Configure repository settings"""
    
    async def execute(self) -> ActionResult:
        try:
            target_repo = self.parameters["target_repo"]
            repo = self.github_client.get_repo(target_repo)
            
            # Update settings
            if "description" in self.parameters:
                repo.edit(description=self.parameters["description"])
            if "homepage" in self.parameters:
                repo.edit(homepage=self.parameters["homepage"])
            if "default_branch" in self.parameters:
                repo.edit(default_branch=self.parameters["default_branch"])
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={"configured": True, "target_repo": target_repo}
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=str(e)
            )
