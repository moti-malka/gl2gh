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
                    
                    # Note: Adding labels, milestone, assignees after PR creation
                    # requires additional API calls not implemented in GitHubClient yet
                    # Would need: PATCH /repos/{owner}/{repo}/issues/{issue_number}
                    
                    # Store ID mapping
                    if gitlab_mr_id:
                        self.set_id_mapping("merge_request", gitlab_mr_id, pr["number"])
                    
                    return ActionResult(
                        success=True,
                        action_id=self.action_id,
                        action_type=self.action_type,
                        outputs={
                            "pr_number": pr["number"],
                            "pr_url": pr["html_url"],
                            "gitlab_mr_id": gitlab_mr_id,
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
