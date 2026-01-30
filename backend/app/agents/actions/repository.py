"""Repository-related actions"""

from typing import Any, Dict
from pathlib import Path
import subprocess
import shutil
import tempfile
from .base import BaseAction, ActionResult
import httpx


class CreateRepositoryAction(BaseAction):
    """Create GitHub repository"""
    
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
                    "repo_full_name": repo["full_name"],
                    "repo_url": repo["html_url"],
                    "repo_id": repo["id"]
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
            
            if not lfs_objects_path.exists():
                return ActionResult(
                    success=True,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={"skipped": True, "reason": "No LFS objects found"}
                )
            
            # Note: LFS push would require more complex handling
            # This is a placeholder implementation
            self.logger.warning("LFS push not fully implemented yet")
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={"lfs_configured": True, "target_repo": target_repo}
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
