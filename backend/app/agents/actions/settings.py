"""Settings-related actions (branch protection, collaborators, webhooks)"""

from typing import Any, Dict
from .base import BaseAction, ActionResult
from github import GithubException


class SetBranchProtectionAction(BaseAction):
    """Set branch protection rules"""
    
    async def execute(self) -> ActionResult:
        try:
            target_repo = self.parameters["target_repo"]
            branch_name = self.parameters["branch"]
            
            repo = self.github_client.get_repo(target_repo)
            branch = repo.get_branch(branch_name)
            
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
            
            # Apply protection
            branch.edit_protection(
                strict=strict_status_checks,
                contexts=contexts if require_status_checks else [],
                enforce_admins=enforce_admins,
                dismissal_users=[],
                dismissal_teams=[],
                dismiss_stale_reviews=dismiss_stale_reviews,
                require_code_owner_reviews=require_code_owner_reviews,
                required_approving_review_count=required_approving_review_count
            )
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "branch": branch_name,
                    "target_repo": target_repo,
                    "protected": True
                }
            )
        except GithubException as e:
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


class AddCollaboratorAction(BaseAction):
    """Add collaborator to repository"""
    
    async def execute(self) -> ActionResult:
        try:
            target_repo = self.parameters["target_repo"]
            username = self.parameters["username"]
            permission = self.parameters.get("permission", "push")  # pull, push, admin, maintain, triage
            
            repo = self.github_client.get_repo(target_repo)
            repo.add_to_collaborators(username, permission)
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "username": username,
                    "permission": permission,
                    "target_repo": target_repo
                }
            )
        except GithubException as e:
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
            insecure_ssl = self.parameters.get("insecure_ssl", False)
            
            if not secret:
                return ActionResult(
                    success=False,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={},
                    error="Webhook secret not provided. User input required."
                )
            
            repo = self.github_client.get_repo(target_repo)
            
            config = {
                "url": url,
                "content_type": content_type,
                "secret": secret,
                "insecure_ssl": "1" if insecure_ssl else "0"  # GitHub API expects string "0" or "1"
            }
            
            hook = repo.create_hook(
                name="web",
                config=config,
                events=events,
                active=active
            )
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "webhook_id": hook.id,
                    "webhook_url": url,
                    "events": events,
                    "target_repo": target_repo,
                    "insecure_ssl": insecure_ssl
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
