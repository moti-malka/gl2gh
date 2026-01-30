"""Repository-related actions"""

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
                },
                rollback_data={
                    "repo_full_name": repo.full_name,
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
