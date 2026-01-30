"""Release-related actions"""

from typing import Any, Dict
from pathlib import Path
from .base import BaseAction, ActionResult


class CreateReleaseAction(BaseAction):
    """Create GitHub release"""
    
    async def execute(self) -> ActionResult:
        try:
            target_repo = self.parameters["target_repo"]
            tag_name = self.parameters["tag"]
            name = self.parameters.get("name", tag_name)
            body = self.parameters.get("body", "")
            draft = self.parameters.get("draft", False)
            prerelease = self.parameters.get("prerelease", False)
            target_commitish = self.parameters.get("target_commitish", "main")
            gitlab_release_id = self.parameters.get("gitlab_release_id")
            
            release = await self.github_client.create_release(
                repo=target_repo,
                tag=tag_name,
                name=name,
                body=body,
                draft=draft,
                prerelease=prerelease,
                target_commitish=target_commitish
            )
            
            # Store ID mapping
            if gitlab_release_id:
                self.set_id_mapping("release", gitlab_release_id, release["id"])
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "release_id": release["id"],
                    "release_url": release["html_url"],
                    "tag_name": tag_name,
                    "gitlab_release_id": gitlab_release_id
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


class UploadReleaseAssetAction(BaseAction):
    """Upload asset to GitHub release"""
    
    async def execute(self) -> ActionResult:
        try:
            target_repo = self.parameters["target_repo"]
            release_tag = self.parameters.get("release_tag")
            gitlab_release_id = self.parameters.get("gitlab_release_id")
            asset_path = Path(self.parameters["asset_path"])
            asset_name = self.parameters.get("asset_name", asset_path.name)
            
            if not asset_path.exists():
                raise FileNotFoundError(f"Asset file not found: {asset_path}")
            
            # Find release by tag or ID mapping
            release_id = None
            if release_tag:
                # Get releases and find by tag
                releases = await self.github_client.list_releases(target_repo)
                for release in releases:
                    if release["tag_name"] == release_tag:
                        release_id = release["id"]
                        break
                if not release_id:
                    raise ValueError(f"Release not found for tag: {release_tag}")
            elif gitlab_release_id:
                release_id = self.get_id_mapping("release", gitlab_release_id)
                if not release_id:
                    raise ValueError(f"Could not find GitHub release for GitLab release {gitlab_release_id}")
            else:
                raise ValueError("Either release_tag or gitlab_release_id must be provided")
            
            # Upload asset
            asset = await self.github_client.upload_release_asset(
                release_id=release_id,
                file_path=str(asset_path),
                repo=target_repo
            )
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "asset_id": asset["id"],
                    "asset_name": asset_name,
                    "release_tag": release_tag
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
