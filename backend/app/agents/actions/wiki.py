"""Wiki-related actions"""

from typing import Any, Dict
from pathlib import Path
import subprocess
import shutil
import tempfile
from .base import BaseAction, ActionResult


class PushWikiAction(BaseAction):
    """Push wiki content to GitHub"""
    
    async def execute(self) -> ActionResult:
        try:
            wiki_content_path = Path(self.parameters["wiki_content_path"])
            target_repo = self.parameters["target_repo"]
            
            if not wiki_content_path.exists():
                return ActionResult(
                    success=True,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={"skipped": True, "reason": "No wiki content found"}
                )
            
            # Get repository to check if wiki is enabled
            owner, repo = target_repo.split("/")
            repo_data = await self.github_client.get_repository(owner, repo)
            
            # Enable wiki if not enabled (requires updating repo settings)
            # Note: GitHubClient doesn't have repo update method yet
            if not repo_data.get("has_wiki"):
                self.logger.warning("Wiki not enabled on repository - manual setup required")
            
            # Clone wiki repository
            wiki_url = f"https://github.com/{target_repo}.wiki.git"
            token = self.context.get("github_token")
            auth_url = wiki_url.replace("https://", f"https://x-access-token:{token}@")
            
            temp_dir = Path(tempfile.mkdtemp(prefix="gl2gh_wiki_"))
            
            try:
                # Clone wiki
                subprocess.run(
                    ["git", "clone", auth_url, str(temp_dir)],
                    check=True,
                    capture_output=True,
                    text=True
                )
                
                # Copy wiki content
                for file in wiki_content_path.glob("*.md"):
                    shutil.copy(file, temp_dir / file.name)
                
                # Commit and push (check if there are changes first)
                result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=temp_dir,
                    check=True,
                    capture_output=True,
                    text=True
                )
                
                if result.stdout.strip():  # Only commit if there are changes
                    subprocess.run(
                        ["git", "add", "."],
                        cwd=temp_dir,
                        check=True,
                        capture_output=True,
                        text=True
                    )
                    
                    subprocess.run(
                        ["git", "commit", "-m", "Migrate wiki content from GitLab"],
                        cwd=temp_dir,
                        check=True,
                        capture_output=True,
                        text=True
                    )
                    
                    subprocess.run(
                        ["git", "push"],
                        cwd=temp_dir,
                        check=True,
                        capture_output=True,
                        text=True
                    )
                    pushed = True
                else:
                    pushed = False  # No changes to push
                
                return ActionResult(
                    success=True,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={"wiki_pushed": pushed, "target_repo": target_repo}
                )
            finally:
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
