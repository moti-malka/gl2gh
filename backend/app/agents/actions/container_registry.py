"""Container registry related actions"""

from typing import Any, Dict
from .base import BaseAction, ActionResult


class ReportContainerImagesAction(BaseAction):
    """Report container images that need manual migration"""
    
    async def execute(self) -> ActionResult:
        """
        Report container images discovered during export.
        
        This action creates documentation and instructions for manual
        image migration, as automated container image transfer requires
        Docker daemon or complex registry API operations.
        """
        try:
            images = self.parameters.get("images", [])
            target_repo = self.parameters.get("target_repo", "")
            
            if not images:
                return ActionResult(
                    success=True,
                    action_id=self.action_id,
                    action_type=self.action_type,
                    outputs={
                        "message": "No container images found",
                        "images_count": 0
                    }
                )
            
            # Build summary
            total_tags = sum(len(img.get('tags', [])) for img in images)
            
            # Create migration instructions
            instructions = self._generate_migration_instructions(images, target_repo)
            
            self.logger.info(
                f"Reported {len(images)} container repositories with {total_tags} tags "
                f"for manual migration"
            )
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "images_count": len(images),
                    "tags_count": total_tags,
                    "instructions": instructions,
                    "note": (
                        "Container images require manual migration. "
                        "See the exported container_registry directory for migration scripts and detailed instructions."
                    )
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
    
    def _generate_migration_instructions(
        self,
        images: list,
        target_repo: str
    ) -> str:
        """Generate migration instructions"""
        instructions = [
            "# Container Registry Migration Instructions",
            "",
            f"## Summary",
            f"- Repositories: {len(images)}",
            f"- Total Tags: {sum(len(img.get('tags', [])) for img in images)}",
            "",
            "## Migration Methods",
            "",
            "### Method 1: Use Docker (Recommended)",
            "```bash",
            "# Login to both registries",
            'echo "$GITLAB_TOKEN" | docker login registry.gitlab.com -u oauth2 --password-stdin',
            'echo "$GITHUB_TOKEN" | docker login ghcr.io -u $GITHUB_USER --password-stdin',
            "",
            "# Pull, tag, and push each image",
        ]
        
        # Add example for first image
        if images and images[0].get('tags'):
            first_image = images[0]
            first_tag = first_image['tags'][0]
            gitlab_url = first_tag.get('gitlab_image_url', '')
            github_url = first_tag.get('suggested_github_url', '')
            
            if gitlab_url and github_url:
                instructions.extend([
                    f"docker pull {gitlab_url}",
                    f"docker tag {gitlab_url} {github_url}",
                    f"docker push {github_url}",
                ])
        
        instructions.extend([
            "```",
            "",
            "### Method 2: Rebuild from Source",
            "Re-run your CI/CD pipelines with updated registry URLs.",
            "",
            "Update your workflow to push to GHCR:",
            "```yaml",
            "- name: Build and push",
            "  run: |",
            "    docker build -t ghcr.io/${{ github.repository }}:${{ github.sha }} .",
            "    docker push ghcr.io/${{ github.repository }}:${{ github.sha }}",
            "```",
            "",
            "## Image List",
            ""
        ])
        
        # Add list of all images
        for i, img in enumerate(images, 1):
            repo_path = img.get('repository_path', 'unknown')
            tag_count = len(img.get('tags', []))
            instructions.append(f"{i}. {repo_path} ({tag_count} tags)")
        
        return "\n".join(instructions)


class ConfigureGHCRAction(BaseAction):
    """Configure GitHub Container Registry settings"""
    
    async def execute(self) -> ActionResult:
        """
        Document GHCR configuration steps.
        
        Note: This action provides documentation as GHCR setup
        requires manual steps (package visibility, permissions).
        """
        try:
            target_repo = self.parameters.get("target_repo", "")
            
            instructions = f"""
# GitHub Container Registry (GHCR) Setup

## Prerequisites
1. GitHub repository: {target_repo}
2. GitHub personal access token with `write:packages` scope

## Configuration Steps

### 1. Authenticate with GHCR
```bash
echo "$GITHUB_TOKEN" | docker login ghcr.io -u $GITHUB_USER --password-stdin
```

### 2. Configure Package Visibility
- Navigate to https://github.com/{target_repo}/packages
- For each package, go to Package settings
- Update visibility (public/private) as needed
- Configure access permissions

### 3. Update CI/CD Secrets
Add these secrets to your repository:
- `GHCR_TOKEN` or use `GITHUB_TOKEN` (automatically available in workflows)

### 4. Update Workflow
```yaml
name: Build and Push to GHCR

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{{{ github.actor }}}}
          password: ${{{{ secrets.GITHUB_TOKEN }}}}
      
      - name: Build and push
        run: |
          docker build -t ghcr.io/${{{{ github.repository }}}}:${{{{ github.sha }}}} .
          docker push ghcr.io/${{{{ github.repository }}}}:${{{{ github.sha }}}}
```

## Documentation
- [GHCR Documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Docker Login Action](https://github.com/docker/login-action)
"""
            
            self.logger.info(f"Generated GHCR configuration instructions for {target_repo}")
            
            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type,
                outputs={
                    "instructions": instructions,
                    "note": "GHCR configuration requires manual setup steps"
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
