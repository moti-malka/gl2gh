"""Issue-related actions"""

from typing import Any, Dict
from .base import BaseAction, ActionResult
from github import GithubException


class CreateLabelAction(BaseAction):
    """Create label"""
    
    async def execute(self) -> ActionResult:
        try:
            target_repo = self.parameters["target_repo"]
            name = self.parameters["name"]
            color = self.parameters.get("color", "000000")
            description = self.parameters.get("description", "")
            
            repo = self.github_client.get_repo(target_repo)
            
            try:
                label = repo.create_label(name=name, color=color, description=description)
                return ActionResult(
                    success=True,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={"label_name": name, "label_id": label.id},
                    rollback_data={"target_repo": target_repo, "label_name": name}
                )
            except GithubException as e:
                if e.status == 422:
                    # Label already exists
                    self.logger.warning(f"Label {name} already exists")
                    return ActionResult(
                        success=True,
                        action_id=self.action_id,
                        action_type=self.action_type,
                        outputs={"label_name": name, "exists": True}
                    )
                raise
        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=str(e)
            )
    
    async def rollback(self, rollback_data: Dict[str, Any]) -> bool:
        """Rollback label creation by deleting it"""
        try:
            target_repo = rollback_data.get("target_repo")
            label_name = rollback_data.get("label_name")
            
            if not target_repo or not label_name:
                self.logger.error("Missing target_repo or label_name in rollback_data")
                return False
            
            self.logger.info(f"Rolling back: Deleting label {label_name} from {target_repo}")
            repo = self.github_client.get_repo(target_repo)
            label = repo.get_label(label_name)
            label.delete()
            self.logger.info(f"Successfully deleted label {label_name}")
            return True
        except GithubException as e:
            if e.status == 404:
                self.logger.warning(f"Label {label_name} not found during rollback")
                return True
            self.logger.error(f"Failed to rollback label creation: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to rollback label creation: {str(e)}")
            return False


class CreateMilestoneAction(BaseAction):
    """Create milestone"""
    
    async def execute(self) -> ActionResult:
        try:
            target_repo = self.parameters["target_repo"]
            title = self.parameters["title"]
            description = self.parameters.get("description", "")
            due_date = self.parameters.get("due_date")
            state = self.parameters.get("state", "open")
            
            repo = self.github_client.get_repo(target_repo)
            
            milestone = repo.create_milestone(title=title, description=description)
            
            # Set due date if provided
            if due_date:
                milestone.edit(title=title, due_on=due_date)
            
            # Set state if closed
            if state == "closed":
                milestone.edit(state="closed")
            
            # Store ID mapping
            gitlab_id = self.parameters.get("gitlab_milestone_id")
            if gitlab_id:
                self.set_id_mapping("milestone", gitlab_id, milestone.number)
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "milestone_title": title,
                    "milestone_number": milestone.number,
                    "gitlab_id": gitlab_id
                },
                rollback_data={
                    "target_repo": target_repo,
                    "milestone_number": milestone.number
                }
            )
        except GithubException as e:
            if e.status == 422:
                # Milestone already exists
                self.logger.warning(f"Milestone {title} already exists")
                return ActionResult(
                    success=True,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={"milestone_title": title, "exists": True}
                )
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=str(e)
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
        """Rollback milestone creation by deleting it"""
        try:
            target_repo = rollback_data.get("target_repo")
            milestone_number = rollback_data.get("milestone_number")
            
            if not target_repo or not milestone_number:
                self.logger.error("Missing target_repo or milestone_number in rollback_data")
                return False
            
            self.logger.info(f"Rolling back: Deleting milestone #{milestone_number} from {target_repo}")
            repo = self.github_client.get_repo(target_repo)
            milestone = repo.get_milestone(milestone_number)
            milestone.delete()
            self.logger.info(f"Successfully deleted milestone #{milestone_number}")
            return True
        except GithubException as e:
            if e.status == 404:
                self.logger.warning(f"Milestone #{milestone_number} not found during rollback")
                return True
            self.logger.error(f"Failed to rollback milestone creation: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to rollback milestone creation: {str(e)}")
            return False


class CreateIssueAction(BaseAction):
    """Create issue with attribution"""
    
    async def execute(self) -> ActionResult:
        try:
            target_repo = self.parameters["target_repo"]
            title = self.parameters["title"]
            body = self.parameters.get("body", "")
            labels = self.parameters.get("labels", [])
            milestone_number = self.parameters.get("milestone")
            assignees = self.parameters.get("assignees", [])
            gitlab_issue_id = self.parameters.get("gitlab_issue_id")
            
            # Add attribution to body if original author is specified
            original_author = self.parameters.get("original_author")
            if original_author:
                attribution = f"\n\n---\n*Originally created by @{original_author} on GitLab*"
                body = body + attribution
            
            repo = self.github_client.get_repo(target_repo)
            
            # Create issue
            issue = repo.create_issue(
                title=title,
                body=body,
                labels=labels,
                milestone=repo.get_milestone(milestone_number) if milestone_number else None,
                assignees=assignees
            )
            
            # Store ID mapping
            if gitlab_issue_id:
                self.set_id_mapping("issue", gitlab_issue_id, issue.number)
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "issue_number": issue.number,
                    "issue_url": issue.html_url,
                    "gitlab_issue_id": gitlab_issue_id
                },
                rollback_data={
                    "target_repo": target_repo,
                    "issue_number": issue.number
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
        """Rollback issue creation by closing it (issues cannot be deleted via API)"""
        try:
            target_repo = rollback_data.get("target_repo")
            issue_number = rollback_data.get("issue_number")
            
            if not target_repo or not issue_number:
                self.logger.error("Missing target_repo or issue_number in rollback_data")
                return False
            
            self.logger.info(f"Rolling back: Closing issue #{issue_number} in {target_repo}")
            repo = self.github_client.get_repo(target_repo)
            issue = repo.get_issue(issue_number)
            issue.edit(state="closed")
            # Add a comment explaining the rollback
            issue.create_comment("🔄 This issue was closed as part of a migration rollback.")
            self.logger.info(f"Successfully closed issue #{issue_number}")
            return True
        except GithubException as e:
            if e.status == 404:
                self.logger.warning(f"Issue #{issue_number} not found during rollback")
                return True
            self.logger.error(f"Failed to rollback issue creation: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to rollback issue creation: {str(e)}")
            return False


class AddIssueCommentAction(BaseAction):
    """Add comment to issue"""
    
    async def execute(self) -> ActionResult:
        try:
            target_repo = self.parameters["target_repo"]
            issue_number = self.parameters.get("issue_number")
            gitlab_issue_id = self.parameters.get("gitlab_issue_id")
            body = self.parameters["body"]
            
            # Resolve issue number from mapping if needed
            if not issue_number and gitlab_issue_id:
                issue_number = self.get_id_mapping("issue", gitlab_issue_id)
            
            if not issue_number:
                raise ValueError(f"Could not resolve issue number for GitLab issue {gitlab_issue_id}")
            
            # Add attribution if original author specified
            original_author = self.parameters.get("original_author")
            if original_author:
                attribution = f"\n\n*Originally posted by @{original_author} on GitLab*"
                body = body + attribution
            
            repo = self.github_client.get_repo(target_repo)
            issue = repo.get_issue(issue_number)
            comment = issue.create_comment(body)
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "comment_id": comment.id,
                    "issue_number": issue_number
                },
                reversible=False  # Comments cannot be deleted via API
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
        """Comments cannot be deleted via GitHub API"""
        return False
