"""Repository-related actions"""

import json
from typing import Any, Dict
from pathlib import Path
import subprocess
import shutil
import tempfile
from .base import BaseAction, ActionResult
import httpx


class CreateRepositoryAction(BaseAction):
    """Create GitHub repository"""
    
    async def simulate(self) -> ActionResult:
        """Simulate repository creation"""
        try:
            org_or_user = self.parameters.get("org") or self.parameters.get("owner")
            repo_name = self.parameters["name"]
            repo_full_name = f"{org_or_user}/{repo_name}"
            
            # Check if repository already exists
            try:
                repo = self.github_client.get_repo(repo_full_name)
                # Repository exists
                return ActionResult(
                    success=True,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={"repo_full_name": repo_full_name, "exists": True},
                    simulated=True,
                    simulation_outcome="would_skip",
                    simulation_message=f"Repository '{repo_full_name}' already exists, would skip creation"
                )
            except GithubException as e:
                if e.status == 404:
                    # Repository doesn't exist, would be created
                    return ActionResult(
                        success=True,
                        action_id=self.action_id,
                        action_type=self.action_type,
                        outputs={"repo_full_name": repo_full_name},
                        simulated=True,
                        simulation_outcome="would_create",
                        simulation_message=f"Would create repository '{repo_full_name}'"
                    )
                else:
                    # Some other error
                    return ActionResult(
                        success=False,
                        action_id=self.action_id,
                        action_type=self.action_type,
                        outputs={},
                        error=f"Would fail to create repository: {str(e)}",
                        simulated=True,
                        simulation_outcome="would_fail",
                        simulation_message=f"Would fail: {str(e)}"
                    )
        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=str(e),
                simulated=True,
                simulation_outcome="would_fail",
                simulation_message=f"Would fail: {str(e)}"
            )
    
    async def execute(self) -> ActionResult:
        try:
            org_or_user = self.parameters.get("org") or self.parameters.get("owner")
            repo_name = self.parameters["name"]
            
            # Try to create repository (org or user)
            try:
                repo = await self.github_client.create_repository(
                    org=org_or_user,
                    name=repo_name,
                    description=self.parameters.get("description", ""),
                    homepage=self.parameters.get("homepage", ""),
                    private=self.parameters.get("private", True),
                    has_issues=self.parameters.get("has_issues", True),
                    has_projects=self.parameters.get("has_projects", True),
                    has_wiki=self.parameters.get("has_wiki", True),
                    auto_init=self.parameters.get("auto_init", False),
                    topics=self.parameters.get("topics", [])
                )
            except httpx.HTTPStatusError as e:
                # If organization not found (404), try without org (as user repo)
                if e.response.status_code == 404:
                    repo = await self.github_client.create_repository(
                        org=None,
                        name=repo_name,
                        description=self.parameters.get("description", ""),
                        homepage=self.parameters.get("homepage", ""),
                        private=self.parameters.get("private", True),
                        has_issues=self.parameters.get("has_issues", True),
                        has_projects=self.parameters.get("has_projects", True),
                        has_wiki=self.parameters.get("has_wiki", True),
                        auto_init=self.parameters.get("auto_init", False),
                        topics=self.parameters.get("topics", [])
                    )
                else:
                    raise
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "repo_full_name": repo.full_name,
                    "repo_url": repo.html_url,
                    "repo_id": repo.id
                },
                rollback_data={
                    "repo_full_name": repo.full_name,
                    "repo_id": repo.id
                }
            )
        except httpx.HTTPStatusError as e:
            # Check if repo already exists
            if e.response.status_code == 422:
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
    
    async def rollback(self, rollback_data: Dict[str, Any]) -> bool:
        """Rollback repository creation by deleting it"""
        try:
            repo_full_name = rollback_data.get("repo_full_name")
            if not repo_full_name:
                self.logger.error("No repo_full_name in rollback_data")
                return False
            
            self.logger.info(f"Rolling back: Deleting repository {repo_full_name}")
            repo = self.github_client.get_repo(repo_full_name)
            repo.delete()
            self.logger.info(f"Successfully deleted repository {repo_full_name}")
            return True
        except GithubException as e:
            if e.status == 404:
                # Repository already deleted or doesn't exist
                self.logger.warning(f"Repository {repo_full_name} not found during rollback")
                return True
            self.logger.error(f"Failed to rollback repository creation: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to rollback repository creation: {str(e)}")
            return False


class PushCodeAction(BaseAction):
    """Push git bundle to GitHub repository"""
    
    async def execute(self) -> ActionResult:
        try:
            bundle_path = Path(self.parameters["bundle_path"])
            target_repo = self.parameters["target_repo"]
            
            if not bundle_path.exists():
                raise FileNotFoundError(f"Bundle file not found: {bundle_path}")
            
            # Get repository
            owner, repo = target_repo.split("/")
            repo_data = await self.github_client.get_repository(owner, repo)
            clone_url = repo_data["clone_url"]
            
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
                    outputs={"pushed": True, "target_repo": target_repo},
                    reversible=False  # Code push cannot be reversed
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
    
    def is_reversible(self) -> bool:
        """Code push cannot be reversed - history is permanent"""
        return False


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
                    text=True,
                    timeout=300  # 5 minutes for clone
                )
                
                # Install Git LFS in the repository
                subprocess.run(
                    ["git", "lfs", "install"],
                    cwd=temp_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30  # 30 seconds for install
                )
                
                # Copy LFS objects to the cloned repository
                lfs_storage_src = lfs_objects_path / "objects"
                if lfs_storage_src.exists():
                    lfs_storage_dst = temp_dir / ".git" / "lfs" / "objects"
                    lfs_storage_dst.mkdir(parents=True, exist_ok=True)
                    
                    # Copy all LFS objects
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
                # Cleanup temp directory (errors are suppressed to avoid token exposure)
                if temp_dir.exists():
                    try:
                        shutil.rmtree(temp_dir)
                    except Exception:
                        # Suppress cleanup errors to avoid potential token exposure in paths
                        pass
                    
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
            
            # Note: GitHubClient doesn't support repository settings updates
            # This would require additional REST API endpoints
            self.logger.warning("Repository configuration not implemented - manual setup required")
            
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={"target_repo": target_repo},
                error="Repository settings updates not supported yet - manual setup required"
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=str(e)
            )


class UpdateGitmodulesAction(BaseAction):
    """Update .gitmodules file with rewritten URLs"""
    
    async def execute(self) -> ActionResult:
        try:
            target_repo = self.parameters["target_repo"]
            gitmodules_content = self.parameters["gitmodules_content"]
            
            repo = self.github_client.get_repo(target_repo)
            
            # Try to get existing .gitmodules file
            try:
                contents = repo.get_contents(".gitmodules")
                # Update existing file
                repo.update_file(
                    ".gitmodules",
                    "Update submodule URLs for GitHub migration",
                    gitmodules_content,
                    contents.sha
                )
                action = "updated"
            except GithubException as e:
                if e.status == 404:
                    # File doesn't exist, create it
                    repo.create_file(
                        ".gitmodules",
                        "Add .gitmodules file with updated URLs",
                        gitmodules_content
                    )
                    action = "created"
                else:
                    raise
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "gitmodules_updated": True,
                    "target_repo": target_repo,
                    "action": action
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
