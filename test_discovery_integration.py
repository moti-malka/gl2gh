#!/usr/bin/env python3
"""
Integration test for Discovery Agent

This script tests the discovery agent with a mock GitLab setup
to verify all components work together correctly.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import sys
import os

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.agents.discovery_agent import DiscoveryAgent
from app.clients.gitlab_client import GitLabClient


async def test_discovery_integration():
    """Integration test for discovery agent"""
    
    print("=" * 60)
    print("Discovery Agent Integration Test")
    print("=" * 60)
    
    # Create temporary output directory
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"\nUsing temp directory: {tmpdir}")
        
        # Create discovery agent
        agent = DiscoveryAgent()
        print("✓ Discovery agent created")
        
        # Mock GitLab client
        with patch('app.clients.gitlab_client.GitLabClient') as MockClient:
            mock_client = Mock()
            MockClient.return_value.__enter__.return_value = mock_client
            
            # Setup mock responses
            mock_client.list_projects.return_value = [
                {
                    "id": 1,
                    "name": "test-project",
                    "path_with_namespace": "testgroup/test-project",
                    "description": "Test project for integration",
                    "visibility": "private",
                    "archived": False,
                    "created_at": "2024-01-01T00:00:00Z",
                    "last_activity_at": "2024-01-15T00:00:00Z",
                    "web_url": "https://gitlab.com/testgroup/test-project",
                    "default_branch": "main"
                }
            ]
            
            # Repository components
            mock_client.list_branches.return_value = [
                {"name": "main"},
                {"name": "develop"}
            ]
            mock_client.list_tags.return_value = [
                {"name": "v1.0.0"},
                {"name": "v1.1.0"}
            ]
            mock_client.get_commits.return_value = [
                {"id": "abc123", "message": "Initial commit"}
            ]
            
            # CI/CD components
            mock_client.has_ci_config.return_value = True
            mock_client.list_pipelines.return_value = [
                {"id": 1, "status": "success"}
            ]
            mock_client.list_pipeline_schedules.return_value = [
                {"id": 1, "description": "Nightly build"}
            ]
            mock_client.list_environments.return_value = [
                {"name": "production"},
                {"name": "staging"}
            ]
            mock_client.list_variables.return_value = [
                {"key": "API_KEY", "protected": True}
            ]
            
            # Issues and MRs
            mock_client.list_issues.return_value = [
                {"id": 1, "title": "Issue 1"},
                {"id": 2, "title": "Issue 2"}
            ]
            mock_client.list_merge_requests.return_value = [
                {"id": 1, "title": "MR 1"}
            ]
            
            # Wiki
            mock_client.has_wiki.return_value = True
            mock_client.get_wiki_pages.return_value = [
                {"title": "Home"}
            ]
            
            # Releases and Packages
            mock_client.list_releases.return_value = [
                {"tag_name": "v1.0.0"}
            ]
            mock_client.has_packages.return_value = True
            mock_client.list_packages.return_value = [
                {"name": "package1"}
            ]
            
            # Webhooks
            mock_client.list_hooks.return_value = [
                {"url": "https://example.com/hook"}
            ]
            
            # LFS
            mock_client.has_lfs.return_value = True
            
            # Protected resources
            mock_client.list_protected_branches.return_value = [
                {"name": "main"}
            ]
            mock_client.list_protected_tags.return_value = [
                {"name": "v*"}
            ]
            
            # Deploy keys
            mock_client.list_deploy_keys.return_value = [
                {"title": "Deploy key 1"}
            ]
            
            print("✓ Mock GitLab client configured")
            
            # Prepare inputs
            inputs = {
                "gitlab_url": "https://gitlab.com",
                "gitlab_token": "glpat-test-token-12345",
                "output_dir": tmpdir
            }
            
            # Validate inputs
            print("\nValidating inputs...")
            is_valid = agent.validate_inputs(inputs)
            print(f"{'✓' if is_valid else '✗'} Input validation: {is_valid}")
            
            if not is_valid:
                print("✗ Input validation failed")
                return False
            
            # Run discovery
            print("\nRunning discovery...")
            result = await agent.execute(inputs)
            
            # Check result
            status = result.get("status")
            print(f"{'✓' if status == 'success' else '✗'} Discovery status: {status}")
            
            if status != "success":
                print(f"✗ Discovery failed: {result.get('error')}")
                return False
            
            # Check outputs
            outputs = result.get("outputs", {})
            print(f"✓ Projects discovered: {len(outputs.get('discovered_projects', []))}")
            
            # Check artifacts
            artifacts = result.get("artifacts", [])
            print(f"✓ Artifacts generated: {len(artifacts)}")
            
            # Verify artifact files exist
            print("\nVerifying artifacts:")
            for artifact_path in artifacts:
                artifact_file = Path(artifact_path)
                exists = artifact_file.exists()
                size = artifact_file.stat().st_size if exists else 0
                print(f"  {'✓' if exists else '✗'} {artifact_file.name} ({size} bytes)")
            
            # Load and verify inventory.json
            inventory_path = Path(tmpdir) / "inventory.json"
            if inventory_path.exists():
                with open(inventory_path) as f:
                    inventory = json.load(f)
                print(f"\n✓ Inventory loaded: {inventory['projects_count']} projects")
                
                # Check first project has all components
                if inventory['projects']:
                    project = inventory['projects'][0]
                    components = project.get('components', {})
                    print(f"✓ Components detected: {len(components)}/14")
                    
                    # List detected components
                    for comp_name, comp_data in components.items():
                        enabled = comp_data.get('enabled', False)
                        status_icon = '✓' if enabled else '✗'
                        print(f"    {status_icon} {comp_name}")
            
            # Load and verify coverage.json
            coverage_path = Path(tmpdir) / "coverage.json"
            if coverage_path.exists():
                with open(coverage_path) as f:
                    coverage = json.load(f)
                print(f"\n✓ Coverage report generated")
                print(f"  Total projects: {coverage['summary']['total_projects']}")
                
                # Show component coverage
                for comp_name, comp_stats in list(coverage['summary']['components'].items())[:5]:
                    enabled = comp_stats['enabled_count']
                    with_data = comp_stats['projects_with_data']
                    print(f"  {comp_name}: {enabled} enabled, {with_data} with data")
            
            # Load and verify readiness.json
            readiness_path = Path(tmpdir) / "readiness.json"
            if readiness_path.exists():
                with open(readiness_path) as f:
                    readiness = json.load(f)
                print(f"\n✓ Readiness assessment generated")
                print(f"  Ready: {readiness['summary']['ready']}")
                print(f"  Needs review: {readiness['summary']['needs_review']}")
                print(f"  Complex: {readiness['summary']['complex']}")
            
            print("\n" + "=" * 60)
            print("✓ Integration test PASSED")
            print("=" * 60)
            return True


if __name__ == "__main__":
    try:
        result = asyncio.run(test_discovery_integration())
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"\n✗ Integration test FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
