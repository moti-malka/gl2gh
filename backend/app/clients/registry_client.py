"""Container Registry Client for image discovery and metadata export"""

from typing import Any, Dict, List, Optional
from pathlib import Path
import json
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RegistryClient:
    """
    Client for container registry operations.
    
    Handles:
    - Image discovery from GitLab Container Registry
    - Metadata export (image names, tags, sizes, digests)
    - Registry URL transformations
    
    Note: This implementation focuses on metadata export (Option C).
    Actual image transfer would require Docker daemon or registry v2 API implementation.
    """
    
    def __init__(self, gitlab_client: Any):
        """
        Initialize registry client.
        
        Args:
            gitlab_client: GitLabClient instance for API access
        """
        self.gitlab_client = gitlab_client
        self.logger = get_logger(__name__)
    
    async def discover_images(self, project_id: int, project_path: str) -> List[Dict[str, Any]]:
        """
        Discover all container images and tags for a project.
        
        Args:
            project_id: GitLab project ID
            project_path: Project path (e.g., 'namespace/project')
            
        Returns:
            List of images with metadata including repositories and tags
        """
        images = []
        
        try:
            # Get all registry repositories for the project
            repositories = await self.gitlab_client.list_registry_repositories(project_id)
            
            if not repositories:
                self.logger.info(f"No container registry repositories found for project {project_id}")
                return images
            
            # For each repository, get all tags
            for repo in repositories:
                repo_id = repo.get('id')
                repo_path = repo.get('path', '')
                location = repo.get('location', '')
                
                # Get tags for this repository
                tags = await self.gitlab_client.list_registry_tags(project_id, repo_id)
                
                # Build image metadata
                image_data = {
                    'repository_id': repo_id,
                    'repository_path': repo_path,
                    'location': location,
                    'gitlab_registry_url': location,
                    'suggested_github_url': self._transform_to_ghcr_url(repo_path, project_path),
                    'tags': []
                }
                
                # Add tag information
                for tag in tags:
                    tag_info = {
                        'name': tag.get('name', ''),
                        'digest': tag.get('digest', ''),
                        'total_size': tag.get('total_size', 0),
                        'created_at': tag.get('created_at', ''),
                        'short_revision': tag.get('short_revision', ''),
                        'gitlab_image_url': f"{location}:{tag.get('name', '')}"
                    }
                    
                    # Add suggested GitHub GHCR URL
                    github_url = self._transform_to_ghcr_url(repo_path, project_path)
                    tag_info['suggested_github_url'] = f"{github_url}:{tag.get('name', '')}"
                    
                    image_data['tags'].append(tag_info)
                
                images.append(image_data)
                
                self.logger.info(
                    f"Found {len(tags)} tags in repository {repo_path}"
                )
            
            self.logger.info(
                f"Discovered {len(images)} container repositories with "
                f"{sum(len(img['tags']) for img in images)} total tags"
            )
            
        except Exception as e:
            self.logger.error(f"Error discovering images: {e}")
            raise
        
        return images
    
    def _transform_to_ghcr_url(self, gitlab_repo_path: str, project_path: str) -> str:
        """
        Transform GitLab registry URL to GitHub GHCR URL.
        
        GitLab format: registry.gitlab.com/namespace/project/image
        GitHub format: ghcr.io/owner/repo/image
        
        Args:
            gitlab_repo_path: Full GitLab registry path
            project_path: Project path (namespace/project)
            
        Returns:
            Suggested GHCR URL
        """
        # Extract the image name part after the project path
        # Example: registry.gitlab.com/ns/proj/backend -> backend
        # The repo path typically includes the project path, so extract what comes after
        
        if gitlab_repo_path.startswith('registry.gitlab.com/'):
            # Remove registry.gitlab.com/ prefix
            path_part = gitlab_repo_path.replace('registry.gitlab.com/', '')
            
            # Try to extract image name after project path
            if project_path in path_part:
                # Get everything after project_path
                image_part = path_part.replace(project_path, '').strip('/')
                if image_part:
                    # There's a subpath (e.g., /backend)
                    return f"ghcr.io/{project_path}/{image_part}".lower()
                else:
                    # No subpath, just use project path
                    return f"ghcr.io/{project_path}".lower()
            else:
                # Can't parse, use as-is with ghcr.io prefix
                return f"ghcr.io/{path_part}".lower()
        
        # Fallback: assume it's just the project path
        return f"ghcr.io/{project_path}".lower()
    
    def export_image_metadata(
        self,
        images: List[Dict[str, Any]],
        output_path: Path
    ) -> Dict[str, Any]:
        """
        Export container image metadata to JSON file.
        
        Args:
            images: List of images from discover_images()
            output_path: Path to output JSON file
            
        Returns:
            Export summary with counts
        """
        try:
            # Ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create export data
            export_data = {
                'summary': {
                    'total_repositories': len(images),
                    'total_tags': sum(len(img['tags']) for img in images),
                    'migration_instructions': (
                        'Container images must be manually migrated or rebuilt. '
                        'Use docker pull/tag/push or re-run CI/CD pipelines with updated registry URLs.'
                    )
                },
                'repositories': images
            }
            
            # Write to file
            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            self.logger.info(
                f"Exported metadata for {len(images)} repositories "
                f"to {output_path}"
            )
            
            return {
                'success': True,
                'repositories': len(images),
                'tags': export_data['summary']['total_tags'],
                'output_file': str(output_path)
            }
            
        except Exception as e:
            self.logger.error(f"Error exporting image metadata: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_migration_script(
        self,
        images: List[Dict[str, Any]],
        output_path: Path,
        gitlab_token: str = "GITLAB_TOKEN",
        github_token: str = "GITHUB_TOKEN"
    ) -> bool:
        """
        Generate a shell script to help with manual image migration.
        
        Args:
            images: List of images from discover_images()
            output_path: Path to output shell script
            gitlab_token: Token variable name for GitLab registry auth
            github_token: Token variable name for GitHub registry auth
            
        Returns:
            True if script generated successfully
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            lines = [
                "#!/bin/bash",
                "# Container Registry Migration Script",
                "# Generated by gl2gh",
                "",
                "# Prerequisites:",
                "# 1. Docker installed and running",
                "# 2. GITLAB_TOKEN environment variable set with GitLab registry access",
                "# 3. GITHUB_TOKEN environment variable set with GHCR write access",
                "",
                "set -e",
                "",
                "# Login to registries",
                f"echo \"${{GITLAB_TOKEN}}\" | docker login registry.gitlab.com -u oauth2 --password-stdin",
                f"echo \"${{GITHUB_TOKEN}}\" | docker login ghcr.io -u ${{GITHUB_USER:-$(whoami)}} --password-stdin",
                "",
                "# Migrate images",
                ""
            ]
            
            for image in images:
                for tag in image['tags']:
                    gitlab_url = tag['gitlab_image_url']
                    github_url = tag['suggested_github_url']
                    
                    lines.extend([
                        f"echo \"Migrating {gitlab_url}...\"",
                        f"docker pull {gitlab_url}",
                        f"docker tag {gitlab_url} {github_url}",
                        f"docker push {github_url}",
                        f"docker rmi {gitlab_url} {github_url}",
                        ""
                    ])
            
            lines.extend([
                "echo \"Migration complete!\"",
                ""
            ])
            
            with open(output_path, 'w') as f:
                f.write('\n'.join(lines))
            
            # Make script executable
            output_path.chmod(0o755)
            
            self.logger.info(f"Generated migration script at {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error generating migration script: {e}")
            return False
