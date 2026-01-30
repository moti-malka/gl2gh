"""Pull request-related actions"""

from typing import Any, Dict
from .base import BaseAction, ActionResult


class CreatePullRequestAction(BaseAction):
    """Create pull request (or issue if branches don't exist)"""
    
    async def execute(self) -> ActionResult:
        try:
            target_repo = self.parameters["target_repo"]
            title = self.parameters["title"]
            body = self.parameters.get("body", "")
            head = self.parameters.get("head")
            base = self.parameters.get("base", "main")
            labels = self.parameters.get("labels", [])
            milestone_number = self.parameters.get("milestone")
            assignees = self.parameters.get("assignees", [])
            gitlab_mr_id = self.parameters.get("gitlab_mr_id")
            
            # Add attribution
            original_author = self.parameters.get("original_author")
            if original_author:
                attribution = f"\n\n---\n*Originally created by @{original_author} on GitLab*"
                body = body + attribution
            
            # Try to create PR if branches exist
            if head:
                try:
                    pr = await self.github_client.create_pull_request(
                        repo=target_repo,
                        title=title,
                        body=body,
                        head=head,
                        base=base
                    )
                    
                    # Store ID mapping
                    if gitlab_mr_id:
                        self.set_id_mapping("merge_request", gitlab_mr_id, pr["number"])
                    
                    # Note: Labels, milestone, and assignees cannot be added via create_pull_request
                    # Would require additional PATCH /repos/{owner}/{repo}/issues/{number} calls
                    warnings = []
                    if labels:
                        warnings.append(f"Labels not added: {labels}")
                    if milestone_number:
                        warnings.append(f"Milestone not set: {milestone_number}")
                    if assignees:
                        warnings.append(f"Assignees not added: {assignees}")
                    
                    return ActionResult(
                        success=True,
                        action_id=self.action_id,
                        action_type=self.action_type,
                        outputs={
                            "pr_number": pr["number"],
                            "pr_url": pr["html_url"],
                            "gitlab_mr_id": gitlab_mr_id,
                            "created_as": "pull_request"
                        },
                        rollback_data={
                            "target_repo": target_repo,
                            "pr_number": pr.number,
                            "created_as": "pull_request"
                        }
                    )
                except Exception as pr_error:
                    # Fall back to creating as issue
                    self.logger.warning(f"Could not create PR, creating as issue: {pr_error}")
            
            # Create as issue if PR creation failed or no head branch
            issue = await self.github_client.create_issue(
                repo=target_repo,
                title=f"[MR] {title}",
                body=f"*This was a merge request on GitLab*\n\n{body}",
                labels=labels,
                milestone=milestone_number,
                assignees=assignees
            )
            
            # Store ID mapping
            if gitlab_mr_id:
                self.set_id_mapping("merge_request", gitlab_mr_id, issue["number"])
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "issue_number": issue["number"],
                    "issue_url": issue["html_url"],
                    "gitlab_mr_id": gitlab_mr_id,
                    "created_as": "issue",
                    "note": "Created as issue because branches do not exist"
                },
                rollback_data={
                    "target_repo": target_repo,
                    "issue_number": issue.number,
                    "created_as": "issue"
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
        """Rollback PR/issue creation by closing it"""
        try:
            from github import GithubException
            
            target_repo = rollback_data.get("target_repo")
            created_as = rollback_data.get("created_as")
            
            if not target_repo or not created_as:
                self.logger.error("Missing target_repo or created_as in rollback_data")
                return False
            
            repo = self.github_client.get_repo(target_repo)
            
            if created_as == "pull_request":
                pr_number = rollback_data.get("pr_number")
                if not pr_number:
                    self.logger.error("Missing pr_number in rollback_data")
                    return False
                
                self.logger.info(f"Rolling back: Closing PR #{pr_number} in {target_repo}")
                pr = repo.get_pull(pr_number)
                pr.edit(state="closed")
                pr.create_issue_comment("🔄 This pull request was closed as part of a migration rollback.")
                self.logger.info(f"Successfully closed PR #{pr_number}")
            else:  # issue
                issue_number = rollback_data.get("issue_number")
                if not issue_number:
                    self.logger.error("Missing issue_number in rollback_data")
                    return False
                
                self.logger.info(f"Rolling back: Closing issue #{issue_number} in {target_repo}")
                issue = repo.get_issue(issue_number)
                issue.edit(state="closed")
                issue.create_comment("🔄 This issue was closed as part of a migration rollback.")
                self.logger.info(f"Successfully closed issue #{issue_number}")
            
            return True
        except GithubException as e:
            if e.status == 404:
                self.logger.warning(f"PR/Issue not found during rollback")
                return True
            self.logger.error(f"Failed to rollback PR/issue creation: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to rollback PR/issue creation: {str(e)}")
            return False


class AddPRCommentAction(BaseAction):
    """Add comment to pull request"""
    
    async def execute(self) -> ActionResult:
        try:
            target_repo = self.parameters["target_repo"]
            pr_number = self.parameters.get("pr_number")
            gitlab_mr_id = self.parameters.get("gitlab_mr_id")
            body = self.parameters["body"]
            
            # Resolve PR number from mapping if needed
            if not pr_number and gitlab_mr_id:
                pr_number = self.get_id_mapping("merge_request", gitlab_mr_id)
            
            if not pr_number:
                raise ValueError(f"Could not resolve PR number for GitLab MR {gitlab_mr_id}")
            
            # Add attribution
            original_author = self.parameters.get("original_author")
            if original_author:
                attribution = f"\n\n*Originally posted by @{original_author} on GitLab*"
                body = body + attribution
            
            # Create comment (works for both PRs and issues)
            comment = await self.github_client.create_issue_comment(
                repo=target_repo,
                issue_num=pr_number,
                body=body
            )
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "comment_id": comment["id"],
                    "pr_number": pr_number
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
