"""Wiki-related actions"""

from typing import Any, Dict
from pathlib import Path
import subprocess
import shutil
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
            
            # Get repository
            repo = self.github_client.get_repo(target_repo)
            
            # Enable wiki if not enabled
            if not repo.has_wiki:
                repo.edit(has_wiki=True)
            
            # Clone wiki repository
            wiki_url = f"https://github.com/{target_repo}.wiki.git"
            token = self.context.get("github_token")
            auth_url = wiki_url.replace("https://", f"https://x-access-token:{token}@")
            
            temp_dir = Path("/tmp") / f"wiki_{self.action_id}"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            try:
                # Clone wiki
                subprocess.run(
                    ["git", "clone", auth_url, str(temp_dir)],
                    check=True,
                    capture_output=True
                )
                
                # Copy wiki content
                for file in wiki_content_path.glob("*.md"):
                    shutil.copy(file, temp_dir / file.name)
                
                # Commit and push
                subprocess.run(
                    ["git", "add", "."],
                    cwd=temp_dir,
                    check=True
                )
                
                subprocess.run(
                    ["git", "commit", "-m", "Migrate wiki content from GitLab"],
                    cwd=temp_dir,
                    check=True
                )
                
                subprocess.run(
                    ["git", "push"],
                    cwd=temp_dir,
                    check=True
                )
                
                return ActionResult(
                    success=True,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={"wiki_pushed": True, "target_repo": target_repo}
                )
            finally:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    
        except subprocess.CalledProcessError as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=f"Git operation failed: {e.stderr if e.stderr else str(e)}"
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={},
                error=str(e)
            )
