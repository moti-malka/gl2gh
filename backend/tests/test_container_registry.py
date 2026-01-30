"""Tests for container registry functionality"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import json

from app.clients.gitlab_client import GitLabClient
from app.clients.registry_client import RegistryClient


@pytest.fixture
def mock_gitlab_client():
    """Create mock GitLab client"""
    client = AsyncMock(spec=GitLabClient)
    return client


@pytest.fixture
def registry_client(mock_gitlab_client):
    """Create registry client with mocked GitLab client"""
    return RegistryClient(mock_gitlab_client)


@pytest.fixture
def sample_repositories():
    """Sample container registry repositories"""
    return [
        {
            'id': 1,
            'path': 'namespace/project',
            'location': 'registry.gitlab.com/namespace/project'
        },
        {
            'id': 2,
            'path': 'namespace/project/backend',
            'location': 'registry.gitlab.com/namespace/project/backend'
        }
    ]


@pytest.fixture
def sample_tags():
    """Sample container registry tags"""
    return [
        {
            'name': 'latest',
            'digest': 'sha256:abc123',
            'total_size': 50000000,
            'created_at': '2024-01-01T00:00:00Z',
            'short_revision': 'abc123'
        },
        {
            'name': 'v1.0.0',
            'digest': 'sha256:def456',
            'total_size': 45000000,
            'created_at': '2024-01-02T00:00:00Z',
            'short_revision': 'def456'
        }
    ]


class TestGitLabClientRegistry:
    """Tests for GitLab client registry methods"""
    
    @pytest.mark.asyncio
    async def test_list_registry_repositories(self):
        """Test listing registry repositories"""
        client = GitLabClient("https://gitlab.com", "test-token")
        
        # Mock the paginated_request to return sample repos
        async def mock_paginated(*args, **kwargs):
            repos = [
                {'id': 1, 'path': 'ns/proj'},
                {'id': 2, 'path': 'ns/proj/img'}
            ]
            for repo in repos:
                yield repo
        
        with patch.object(client, 'paginated_request', mock_paginated):
            repos = await client.list_registry_repositories(123)
            
            assert len(repos) == 2
            assert repos[0]['id'] == 1
            assert repos[1]['path'] == 'ns/proj/img'
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_list_registry_repositories_error_handling(self):
        """Test error handling when listing repositories fails"""
        client = GitLabClient("https://gitlab.com", "test-token")
        
        # Mock the paginated_request to raise an exception
        async def mock_paginated_error(*args, **kwargs):
            raise Exception("API Error")
        
        with patch.object(client, 'paginated_request', mock_paginated_error):
            repos = await client.list_registry_repositories(123)
            
            # Should return empty list on error
            assert repos == []
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_list_registry_tags(self):
        """Test listing registry tags"""
        client = GitLabClient("https://gitlab.com", "test-token")
        
        # Mock the paginated_request to return sample tags
        async def mock_paginated(*args, **kwargs):
            tags = [
                {'name': 'latest', 'digest': 'sha256:abc'},
                {'name': 'v1.0', 'digest': 'sha256:def'}
            ]
            for tag in tags:
                yield tag
        
        with patch.object(client, 'paginated_request', mock_paginated):
            tags = await client.list_registry_tags(123, 1)
            
            assert len(tags) == 2
            assert tags[0]['name'] == 'latest'
            assert tags[1]['digest'] == 'sha256:def'
        
        await client.close()


class TestRegistryClient:
    """Tests for RegistryClient"""
    
    @pytest.mark.asyncio
    async def test_discover_images(
        self,
        registry_client,
        mock_gitlab_client,
        sample_repositories,
        sample_tags
    ):
        """Test image discovery"""
        # Mock GitLab client methods
        mock_gitlab_client.list_registry_repositories.return_value = sample_repositories
        mock_gitlab_client.list_registry_tags.return_value = sample_tags
        
        # Discover images
        images = await registry_client.discover_images(123, 'namespace/project')
        
        # Verify results
        assert len(images) == 2
        assert images[0]['repository_id'] == 1
        assert len(images[0]['tags']) == 2
        assert images[0]['tags'][0]['name'] == 'latest'
        assert 'suggested_github_url' in images[0]
        assert 'ghcr.io' in images[0]['suggested_github_url']
        
        # Verify GitLab client was called correctly
        mock_gitlab_client.list_registry_repositories.assert_called_once_with(123)
        assert mock_gitlab_client.list_registry_tags.call_count == 2
    
    @pytest.mark.asyncio
    async def test_discover_images_no_repositories(
        self,
        registry_client,
        mock_gitlab_client
    ):
        """Test discovery when no repositories exist"""
        mock_gitlab_client.list_registry_repositories.return_value = []
        
        images = await registry_client.discover_images(123, 'namespace/project')
        
        assert images == []
    
    def test_transform_to_ghcr_url_basic(self, registry_client):
        """Test basic GHCR URL transformation"""
        gitlab_path = 'registry.gitlab.com/namespace/project'
        result = registry_client._transform_to_ghcr_url(
            gitlab_path,
            'namespace/project'
        )
        
        assert result == 'ghcr.io/namespace/project'
    
    def test_transform_to_ghcr_url_with_image_name(self, registry_client):
        """Test GHCR URL transformation with image name"""
        gitlab_path = 'registry.gitlab.com/namespace/project/backend'
        result = registry_client._transform_to_ghcr_url(
            gitlab_path,
            'namespace/project'
        )
        
        assert result == 'ghcr.io/namespace/project/backend'
    
    def test_export_image_metadata(
        self,
        registry_client,
        sample_repositories,
        sample_tags,
        tmp_path
    ):
        """Test exporting image metadata"""
        # Prepare test data
        images = [
            {
                'repository_id': 1,
                'repository_path': 'ns/proj',
                'tags': sample_tags
            }
        ]
        
        output_path = tmp_path / "images.json"
        
        # Export metadata
        result = registry_client.export_image_metadata(images, output_path)
        
        # Verify result
        assert result['success'] is True
        assert result['repositories'] == 1
        assert result['tags'] == 2
        
        # Verify file was created
        assert output_path.exists()
        
        # Verify content
        with open(output_path) as f:
            data = json.load(f)
        
        assert 'summary' in data
        assert data['summary']['total_repositories'] == 1
        assert data['summary']['total_tags'] == 2
        assert 'repositories' in data
    
    def test_generate_migration_script(
        self,
        registry_client,
        sample_tags,
        tmp_path
    ):
        """Test migration script generation"""
        images = [
            {
                'repository_path': 'ns/proj',
                'location': 'registry.gitlab.com/ns/proj',
                'tags': [
                    {
                        'name': 'latest',
                        'gitlab_image_url': 'registry.gitlab.com/ns/proj:latest',
                        'suggested_github_url': 'ghcr.io/ns/proj:latest'
                    }
                ]
            }
        ]
        
        output_path = tmp_path / "migrate.sh"
        
        # Generate script
        result = registry_client.generate_migration_script(images, output_path)
        
        # Verify result
        assert result is True
        assert output_path.exists()
        
        # Verify script content
        content = output_path.read_text()
        assert '#!/bin/bash' in content
        assert 'docker pull registry.gitlab.com/ns/proj:latest' in content
        assert 'docker tag' in content
        assert 'docker push ghcr.io/ns/proj:latest' in content
        
        # Verify script is executable
        assert output_path.stat().st_mode & 0o111  # Check execute bit


class TestCICDTransformerRegistry:
    """Tests for CI/CD transformer registry URL transformations"""
    
    def test_map_ci_variable_registry(self):
        """Test registry variable mapping"""
        from app.utils.transformers import CICDTransformer
        
        transformer = CICDTransformer()
        
        # Test registry variables
        assert transformer._map_ci_variable('CI_REGISTRY') == 'ghcr.io'
        assert transformer._map_ci_variable('CI_REGISTRY_IMAGE') == 'ghcr.io/${{ github.repository }}'
        
        # Test other variables still work
        assert transformer._map_ci_variable('CI_COMMIT_SHA') == '${{ github.sha }}'
    
    def test_transform_registry_urls_in_script(self):
        """Test registry URL transformation in scripts"""
        from app.utils.transformers import CICDTransformer
        
        transformer = CICDTransformer()
        
        # Test script with GitLab registry references
        script = """
docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .
docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
docker pull registry.gitlab.com/namespace/project:latest
"""
        
        result = transformer._transform_registry_urls(script)
        
        # Verify transformations
        assert 'ghcr.io/${{ github.repository }}' in result
        assert '$CI_REGISTRY_IMAGE' not in result
        assert 'ghcr.io/namespace/project:latest' in result
        assert 'registry.gitlab.com' not in result
    
    def test_transform_with_braces(self):
        """Test transformation with braced variables"""
        from app.utils.transformers import CICDTransformer
        
        transformer = CICDTransformer()
        
        script = 'docker push ${CI_REGISTRY_IMAGE}:${CI_COMMIT_SHA}'
        result = transformer._transform_registry_urls(script)
        
        assert 'ghcr.io/${{ github.repository }}' in result
        assert '${CI_REGISTRY_IMAGE}' not in result
    
    def test_cicd_workflow_with_registry(self):
        """Test full CI/CD workflow transformation with registry"""
        from app.utils.transformers import CICDTransformer
        
        transformer = CICDTransformer()
        
        gitlab_ci = {
            'variables': {
                'IMAGE_TAG': '$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA'
            },
            'build': {
                'stage': 'build',
                'image': 'docker:latest',
                'script': [
                    'docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .',
                    'docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA'
                ]
            }
        }
        
        result = transformer.transform({'gitlab_ci_yaml': gitlab_ci})
        
        assert result.success
        workflow = result.data['workflow']
        
        # Check that build job exists
        assert 'build' in workflow['jobs']
        
        # Check that script was transformed
        build_job = workflow['jobs']['build']
        run_step = next(
            (s for s in build_job['steps'] if s.get('name') == 'Run build'),
            None
        )
        
        assert run_step is not None
        assert 'ghcr.io/${{ github.repository }}' in run_step['run']
        assert '$CI_REGISTRY_IMAGE' not in run_step['run']


class TestExportAgentRegistry:
    """Tests for export agent container registry export"""
    
    @pytest.mark.asyncio
    async def test_export_container_registry_disabled(self, tmp_path):
        """Test export when container registry is disabled"""
        from app.agents.export_agent import ExportAgent
        
        agent = ExportAgent()
        
        # Mock GitLab client
        agent.gitlab_client = AsyncMock()
        
        # Project with container registry disabled
        project = {
            'path_with_namespace': 'ns/proj',
            'container_registry_enabled': False
        }
        
        output_dir = tmp_path / "test_export"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / 'container_registry').mkdir(parents=True, exist_ok=True)
        
        result = await agent._export_container_registry(123, project, output_dir)
        
        assert result['success'] is True
        assert result['count'] == 0
        
        # Check that a file was created indicating registry is disabled
        disabled_file = output_dir / 'container_registry' / 'registry_disabled.txt'
        assert disabled_file.exists()
    
    @pytest.mark.asyncio
    async def test_export_container_registry_with_images(self, tmp_path):
        """Test export when images exist"""
        from app.agents.export_agent import ExportAgent
        
        agent = ExportAgent()
        
        # Mock GitLab client
        agent.gitlab_client = AsyncMock()
        agent.gitlab_client.list_registry_repositories.return_value = [
            {'id': 1, 'path': 'ns/proj', 'location': 'registry.gitlab.com/ns/proj'}
        ]
        agent.gitlab_client.list_registry_tags.return_value = [
            {
                'name': 'latest',
                'digest': 'sha256:abc',
                'total_size': 1000000,
                'created_at': '2024-01-01T00:00:00Z'
            }
        ]
        
        # Project with container registry enabled
        project = {
            'path_with_namespace': 'ns/proj',
            'container_registry_enabled': True
        }
        
        output_dir = tmp_path / "test_export_images"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / 'container_registry').mkdir(parents=True, exist_ok=True)
        
        result = await agent._export_container_registry(123, project, output_dir)
        
        assert result['success'] is True
        assert result['count'] == 1
        assert result['tags'] == 1
        
        # Check that files were created
        images_file = output_dir / 'container_registry' / 'images.json'
        script_file = output_dir / 'container_registry' / 'migrate_images.sh'
        readme_file = output_dir / 'container_registry' / 'README.md'
        
        assert images_file.exists()
        assert script_file.exists()
        assert readme_file.exists()
