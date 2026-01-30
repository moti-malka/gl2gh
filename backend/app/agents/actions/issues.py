"""Issue-related actions"""

from typing import Any, Dict
from .base import BaseAction, ActionResult
import httpx


class CreateLabelAction(BaseAction):
    """Create label"""
    
    async def simulate(self) -> ActionResult:
        """Simulate label creation"""
        try:
            target_repo = self.parameters["target_repo"]
            name = self.parameters["name"]
            
            # Check if label already exists
            try:
                repo = self.github_client.get_repo(target_repo)
                label = repo.get_label(name)
                return ActionResult(
                    success=True,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={"label_name": name, "exists": True},
                    simulated=True,
                    simulation_outcome="would_skip",
                    simulation_message=f"Label '{name}' already exists, would skip"
                )
            except GithubException as e:
                if e.status == 404:
                    # Label doesn't exist, would be created
                    return ActionResult(
                        success=True,
                        action_id=self.action_id,
                        action_type=self.action_type,
                        outputs={"label_name": name},
                        simulated=True,
                        simulation_outcome="would_create",
                        simulation_message=f"Would create label: '{name}'"
                    )
                else:
                    raise
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
            target_repo = self.parameters["target_repo"]
            name = self.parameters["name"]
            color = self.parameters.get("color", "000000")
            description = self.parameters.get("description", "")
            
            # Note: GitHubClient doesn't have label creation method yet
            # Would need REST API: POST /repos/{owner}/{repo}/labels
            self.logger.warning(f"Label creation not implemented - will need manual setup for: {name}")
            
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={"label_name": name},
                error="Label creation not supported yet - manual setup required"
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=str(e)
            )


class CreateMilestoneAction(BaseAction):
    """Create milestone"""
    
    async def simulate(self) -> ActionResult:
        """Simulate milestone creation"""
        try:
            target_repo = self.parameters["target_repo"]
            title = self.parameters["title"]
            gitlab_id = self.parameters.get("gitlab_milestone_id")
            
            # Check if milestone with same title already exists
            try:
                repo = self.github_client.get_repo(target_repo)
                milestones = list(repo.get_milestones(state='all'))
                for milestone in milestones:
                    if milestone.title == title:
                        return ActionResult(
                            success=True,
                            action_id=self.action_id,
                            action_type=self.action_type,
                            outputs={"milestone_title": title, "exists": True, "milestone_number": milestone.number},
                            simulated=True,
                            simulation_outcome="would_skip",
                            simulation_message=f"Milestone '{title}' already exists, would skip"
                        )
            except Exception:
                # If we can't check, assume it will be created
                pass
            
            # Milestone doesn't exist, would be created
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={"milestone_title": title, "gitlab_id": gitlab_id},
                simulated=True,
                simulation_outcome="would_create",
                simulation_message=f"Would create milestone: '{title}'"
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
            target_repo = self.parameters["target_repo"]
            title = self.parameters["title"]
            
            # Note: GitHubClient doesn't have milestone creation method yet
            # Would need REST API: POST /repos/{owner}/{repo}/milestones
            self.logger.warning(f"Milestone creation not implemented - will need manual setup for: {title}")
            
            gitlab_id = self.parameters.get("gitlab_milestone_id")
            
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={"milestone_title": title, "gitlab_id": gitlab_id},
                error="Milestone creation not supported yet - manual setup required"
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=str(e)
            )


class CreateIssueAction(BaseAction):
    """Create issue with attribution"""
    
    async def simulate(self) -> ActionResult:
        """Simulate issue creation"""
        try:
            target_repo = self.parameters["target_repo"]
            title = self.parameters["title"]
            gitlab_issue_id = self.parameters.get("gitlab_issue_id")
            
            # Try to check if an issue with same title already exists
            try:
                repo = self.github_client.get_repo(target_repo)
                # Search for open issues with the same title
                existing_issues = list(repo.get_issues(state='all'))
                for issue in existing_issues:
                    if issue.title == title:
                        return ActionResult(
                            success=True,
                            action_id=self.action_id,
                            action_type=self.action_type,
                            outputs={
                                "title": title,
                                "gitlab_issue_id": gitlab_issue_id,
                                "existing_issue_number": issue.number
                            },
                            simulated=True,
                            simulation_outcome="would_skip",
                            simulation_message=f"Issue with title '{title}' already exists as #{issue.number}, would skip"
                        )
            except Exception:
                # If we can't check, assume it will be created
                pass
            
            # In dry-run, we predict the issue will be created
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "title": title,
                    "gitlab_issue_id": gitlab_issue_id
                },
                simulated=True,
                simulation_outcome="would_create",
                simulation_message=f"Would create issue: '{title}' in {target_repo}"
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
            
            # Create issue
            issue = await self.github_client.create_issue(
                repo=target_repo,
                title=title,
                body=body,
                labels=labels,
                milestone=milestone_number,
                assignees=assignees
            )
            
            # Store ID mapping
            if gitlab_issue_id:
                self.set_id_mapping("issue", gitlab_issue_id, issue["number"])
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "issue_number": issue["number"],
                    "issue_url": issue["html_url"],
                    "gitlab_issue_id": gitlab_issue_id
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
            
            comment = await self.github_client.create_issue_comment(
                repo=target_repo,
                issue_num=issue_number,
                body=body
            )
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "comment_id": comment["id"],
                    "issue_number": issue_number
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
