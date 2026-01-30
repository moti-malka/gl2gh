"""Settings-related actions (branch protection, collaborators, webhooks)"""

from typing import Any, Dict
from .base import BaseAction, ActionResult
import httpx


class SetBranchProtectionAction(BaseAction):
    """Set branch protection rules"""
    
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
            
            # Build protection rules
            rules = {
                "required_status_checks": {
                    "strict": strict_status_checks,
                    "contexts": contexts if require_status_checks else []
                } if require_status_checks else None,
                "enforce_admins": enforce_admins,
                "required_pull_request_reviews": {
                    "dismiss_stale_reviews": dismiss_stale_reviews,
                    "require_code_owner_reviews": require_code_owner_reviews,
                    "required_approving_review_count": required_approving_review_count
                },
                "restrictions": None
            }
            
            # Apply protection
            await self.github_client.update_branch_protection(
                repo=target_repo,
                branch=branch_name,
                rules=rules
            )
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "branch": branch_name,
                    "target_repo": target_repo,
                    "protected": True
                },
                rollback_data={
                    "target_repo": target_repo,
                    "branch": branch_name
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
    
    async def rollback(self, rollback_data: Dict[str, Any]) -> bool:
        """Rollback webhook creation by deleting it"""
        try:
            target_repo = rollback_data.get("target_repo")
            webhook_id = rollback_data.get("webhook_id")
            
            if not target_repo or not webhook_id:
                self.logger.error("Missing target_repo or webhook_id in rollback_data")
                return False
            
            self.logger.info(f"Rolling back: Deleting webhook {webhook_id} from {target_repo}")
            repo = self.github_client.get_repo(target_repo)
            hook = repo.get_hook(webhook_id)
            hook.delete()
            self.logger.info(f"Successfully deleted webhook {webhook_id}")
            return True
        except GithubException as e:
            if e.status == 404:
                self.logger.warning(f"Webhook {webhook_id} not found during rollback")
                return True
            self.logger.error(f"Failed to rollback webhook creation: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to rollback webhook creation: {str(e)}")
            return False
