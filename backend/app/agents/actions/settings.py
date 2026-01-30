"""Settings-related actions (branch protection, collaborators, webhooks)"""

from typing import Any, Dict
from .base import BaseAction, ActionResult
import httpx


class SetBranchProtectionAction(BaseAction):
    """Set branch protection rules with full GitLab → GitHub mapping"""
    
    async def execute(self) -> ActionResult:
        try:
            target_repo = self.parameters["target_repo"]
            branch_name = self.parameters["branch"]
            
            # Get protection settings from parameters
            require_code_owner_reviews = self.parameters.get("require_code_owner_reviews", False)
            required_approving_review_count = self.parameters.get("required_approving_review_count", 1)
            dismiss_stale_reviews = self.parameters.get("dismiss_stale_reviews", False)
            require_status_checks = self.parameters.get("require_status_checks", False)
            strict_status_checks = self.parameters.get("strict", False)
            contexts = self.parameters.get("contexts", [])
            enforce_admins = self.parameters.get("enforce_admins", False)
            require_linear_history = self.parameters.get("require_linear_history", False)
            allow_force_pushes = self.parameters.get("allow_force_pushes", False)
            allow_deletions = self.parameters.get("allow_deletions", False)
            required_conversation_resolution = self.parameters.get("required_conversation_resolution", False)
            
            # Get required_status_checks from parameters if provided as dict
            required_status_checks = self.parameters.get("required_status_checks")
            
            # Build protection parameters
            protection_params = {
                "enforce_admins": enforce_admins,
                "required_linear_history": require_linear_history,
                "allow_force_pushes": allow_force_pushes,
                "allow_deletions": allow_deletions,
            }
            
            # Add status checks if required
            if required_status_checks and isinstance(required_status_checks, dict):
                # Status checks provided as dict
                protection_params["strict"] = required_status_checks.get("strict", strict_status_checks)
                protection_params["contexts"] = required_status_checks.get("contexts", [])
            elif require_status_checks or contexts:
                # Individual parameters
                protection_params["strict"] = strict_status_checks
                protection_params["contexts"] = contexts
            
            # Add required reviews
            required_pull_request_reviews = self.parameters.get("required_pull_request_reviews")
            if required_pull_request_reviews:
                # Use provided dict
                protection_params["dismiss_stale_reviews"] = required_pull_request_reviews.get(
                    "dismiss_stale_reviews", dismiss_stale_reviews
                )
                protection_params["require_code_owner_reviews"] = required_pull_request_reviews.get(
                    "require_code_owner_reviews", require_code_owner_reviews
                )
                protection_params["required_approving_review_count"] = required_pull_request_reviews.get(
                    "required_approving_review_count", required_approving_review_count
                )
            else:
                # Use individual parameters
                protection_params["dismiss_stale_reviews"] = dismiss_stale_reviews
                protection_params["require_code_owner_reviews"] = require_code_owner_reviews
                protection_params["required_approving_review_count"] = required_approving_review_count
            
            # Add dismissal restrictions if provided
            protection_params["dismissal_users"] = self.parameters.get("dismissal_users", [])
            protection_params["dismissal_teams"] = self.parameters.get("dismissal_teams", [])
            
            # Apply protection
            branch.edit_protection(**protection_params)
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "branch": branch_name,
                    "target_repo": target_repo,
                    "protected": True,
                    "settings_applied": {
                        "required_reviews": required_approving_review_count,
                        "status_checks": len(contexts) if contexts else 0,
                        "force_push_allowed": allow_force_pushes,
                        "deletions_allowed": allow_deletions
                    }
                }
            )
        except httpx.HTTPStatusError as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=f"Failed to set branch protection: {str(e)}"
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
        """Rollback branch protection by removing it"""
        try:
            target_repo = rollback_data.get("target_repo")
            branch_name = rollback_data.get("branch")
            
            if not target_repo or not branch_name:
                self.logger.error("Missing target_repo or branch in rollback_data")
                return False
            
            self.logger.info(f"Rolling back: Removing branch protection from {branch_name} in {target_repo}")
            repo = self.github_client.get_repo(target_repo)
            branch = repo.get_branch(branch_name)
            branch.remove_protection()
            self.logger.info(f"Successfully removed branch protection from {branch_name}")
            return True
        except GithubException as e:
            if e.status == 404:
                self.logger.warning(f"Branch protection not found during rollback")
                return True
            self.logger.error(f"Failed to rollback branch protection: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to rollback branch protection: {str(e)}")
            return False


class AddCollaboratorAction(BaseAction):
    """Add collaborator to repository"""
    
    async def execute(self) -> ActionResult:
        try:
            target_repo = self.parameters["target_repo"]
            username = self.parameters["username"]
            permission = self.parameters.get("permission", "push")
            
            success = await self.github_client.add_collaborator(
                repo=target_repo,
                username=username,
                permission=permission
            )
            
            if not success:
                raise Exception("Failed to add collaborator")
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "username": username,
                    "permission": permission,
                    "target_repo": target_repo
                },
                rollback_data={
                    "target_repo": target_repo,
                    "username": username
                }
            )
        except httpx.HTTPStatusError as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=f"Failed to add collaborator: {str(e)}"
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
        """Rollback collaborator addition by removing them"""
        try:
            target_repo = rollback_data.get("target_repo")
            username = rollback_data.get("username")
            
            if not target_repo or not username:
                self.logger.error("Missing target_repo or username in rollback_data")
                return False
            
            self.logger.info(f"Rolling back: Removing collaborator {username} from {target_repo}")
            repo = self.github_client.get_repo(target_repo)
            repo.remove_from_collaborators(username)
            self.logger.info(f"Successfully removed collaborator {username}")
            return True
        except GithubException as e:
            if e.status == 404:
                self.logger.warning(f"Collaborator {username} not found during rollback")
                return True
            self.logger.error(f"Failed to rollback collaborator addition: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to rollback collaborator addition: {str(e)}")
            return False


class CreateWebhookAction(BaseAction):
    """Create webhook"""
    
    async def execute(self) -> ActionResult:
        try:
            target_repo = self.parameters["target_repo"]
            url = self.parameters["url"]
            events = self.parameters.get("events", ["push"])
            secret = self.parameters.get("secret")
            content_type = self.parameters.get("content_type", "json")
            active = self.parameters.get("active", True)
            
            if not secret:
                return ActionResult(
                    success=False,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={},
                    error="Webhook secret not provided. User input required."
                )
            
            hook = await self.github_client.create_webhook(
                repo=target_repo,
                url=url,
                events=events,
                secret=secret,
                content_type=content_type,
                active=active
            )
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "webhook_id": hook["id"],
                    "webhook_url": url,
                    "events": events,
                    "target_repo": target_repo
                },
                rollback_data={
                    "target_repo": target_repo,
                    "webhook_id": hook.id
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


class CommitCodeownersAction(BaseAction):
    """Commit CODEOWNERS file to repository"""
    
    async def execute(self) -> ActionResult:
        try:
            target_repo = self.parameters["target_repo"]
            codeowners_content = self.parameters["codeowners_content"]
            branch = self.parameters.get("branch", "main")
            commit_message = self.parameters.get(
                "commit_message", 
                "Add CODEOWNERS file from GitLab approval rules"
            )
            
            repo = self.github_client.get_repo(target_repo)
            
            # CODEOWNERS can be in root, .github/, or docs/
            # We'll use .github/CODEOWNERS as the standard location
            file_path = ".github/CODEOWNERS"
            
            try:
                # Try to get existing CODEOWNERS file
                existing_file = repo.get_contents(file_path, ref=branch)
                # Update existing file
                repo.update_file(
                    path=file_path,
                    message=commit_message,
                    content=codeowners_content,
                    sha=existing_file.sha,
                    branch=branch
                )
                action_taken = "updated"
            except GithubException:
                # File doesn't exist, create it
                repo.create_file(
                    path=file_path,
                    message=commit_message,
                    content=codeowners_content,
                    branch=branch
                )
                action_taken = "created"
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "file_path": file_path,
                    "target_repo": target_repo,
                    "branch": branch,
                    "action": action_taken
                }
            )
        except GithubException as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=f"Failed to commit CODEOWNERS: {str(e)}"
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=str(e)
            )
