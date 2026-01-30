"""Unit tests for BatchOrchestrator - parallel migration support"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.agents.batch_orchestrator import BatchOrchestrator, SharedResources
from app.agents.orchestrator import MigrationMode


@pytest.fixture
def shared_resources():
    """Create shared resources instance"""
    return SharedResources(github_rate_limit=5000)


@pytest.fixture
def batch_orchestrator(shared_resources):
    """Create batch orchestrator instance"""
    return BatchOrchestrator(shared_resources=shared_resources)


@pytest.mark.asyncio
class TestSharedResources:
    """Test cases for SharedResources"""
    
    async def test_user_mapping_cache(self, shared_resources):
        """Test user mapping cache operations"""
        # Initially empty
        mapping = await shared_resources.get_user_mapping("user123")
        assert mapping is None
        
        # Set mapping
        test_mapping = {"gitlab_id": "user123", "github_id": "gh_user"}
        await shared_resources.set_user_mapping("user123", test_mapping)
        
        # Retrieve mapping
        retrieved = await shared_resources.get_user_mapping("user123")
        assert retrieved == test_mapping
    
    async def test_user_mapping_cache_concurrent_access(self, shared_resources):
        """Test concurrent access to user mapping cache"""
        import asyncio
        
        async def set_mapping(user_id: str):
            mapping = {"gitlab_id": user_id, "github_id": f"gh_{user_id}"}
            await shared_resources.set_user_mapping(user_id, mapping)
        
        # Set multiple mappings concurrently
        tasks = [set_mapping(f"user{i}") for i in range(10)]
        await asyncio.gather(*tasks)
        
        # Verify all mappings were set correctly
        for i in range(10):
            mapping = await shared_resources.get_user_mapping(f"user{i}")
            assert mapping is not None
            assert mapping["gitlab_id"] == f"user{i}"


@pytest.mark.asyncio
class TestBatchOrchestrator:
    """Test cases for BatchOrchestrator"""
    
    async def test_batch_migration_single_project(self, batch_orchestrator):
        """Test batch migration with a single project"""
        # Mock the orchestrator's run_migration method
        mock_result = {
            "status": "success",
            "mode": "PLAN_ONLY",
            "started_at": "2024-01-01T00:00:00",
            "finished_at": "2024-01-01T00:10:00",
            "agents": {}
        }
        
        # Patch the AgentOrchestrator class
        from app.agents.orchestrator import AgentOrchestrator
        
        with patch.object(
            AgentOrchestrator,
            'run_migration',
            new_callable=AsyncMock,
            return_value=mock_result
        ):
            project_configs = [
                {
                    "project_id": 123,
                    "gitlab_url": "https://gitlab.com",
                    "gitlab_token": "test-token",
                    "github_token": "test-github-token",
                    "output_dir": "/tmp/test"
                }
            ]
            
            result = await batch_orchestrator.execute_batch_migration(
                project_configs=project_configs,
                mode=MigrationMode.PLAN_ONLY,
                parallel_limit=5
            )
            
            assert result["status"] == "success"
            assert result["total_projects"] == 1
            assert result["successful"] == 1
            assert result["failed"] == 0
            assert len(result["results"]) == 1
            assert result["results"][0]["project_id"] == 123
    
    async def test_batch_migration_multiple_projects(self, batch_orchestrator):
        """Test batch migration with multiple projects"""
        # Mock the orchestrator's run_migration method
        mock_result = {
            "status": "success",
            "mode": "PLAN_ONLY",
            "started_at": "2024-01-01T00:00:00",
            "finished_at": "2024-01-01T00:10:00",
            "agents": {}
        }
        
        from app.agents.orchestrator import AgentOrchestrator
        
        with patch.object(
            AgentOrchestrator,
            'run_migration',
            new_callable=AsyncMock,
            return_value=mock_result
        ):
            project_configs = [
                {
                    "project_id": i,
                    "gitlab_url": "https://gitlab.com",
                    "gitlab_token": "test-token",
                    "github_token": "test-github-token",
                    "output_dir": f"/tmp/test/{i}"
                }
                for i in range(1, 6)  # 5 projects
            ]
            
            result = await batch_orchestrator.execute_batch_migration(
                project_configs=project_configs,
                mode=MigrationMode.PLAN_ONLY,
                parallel_limit=3
            )
            
            assert result["status"] == "success"
            assert result["total_projects"] == 5
            assert result["successful"] == 5
            assert result["failed"] == 0
            assert result["parallel_limit"] == 3
            assert len(result["results"]) == 5
    
    async def test_batch_migration_with_failures(self, batch_orchestrator):
        """Test batch migration with some projects failing"""
        # Create a mock that returns success for even project IDs, failure for odd
        async def mock_run_migration(mode, config, resume_from=None):
            project_id = config.get("project_id")
            if project_id % 2 == 0:
                return {
                    "status": "success",
                    "mode": mode.value,
                    "agents": {}
                }
            else:
                return {
                    "status": "failed",
                    "mode": mode.value,
                    "error": "Simulated failure",
                    "agents": {}
                }
        
        from app.agents.orchestrator import AgentOrchestrator
        
        with patch.object(
            AgentOrchestrator,
            'run_migration',
            new_callable=AsyncMock,
            side_effect=mock_run_migration
        ):
            project_configs = [
                {
                    "project_id": i,
                    "gitlab_url": "https://gitlab.com",
                    "gitlab_token": "test-token",
                    "github_token": "test-github-token",
                    "output_dir": f"/tmp/test/{i}"
                }
                for i in range(1, 6)  # Projects 1-5
            ]
            
            result = await batch_orchestrator.execute_batch_migration(
                project_configs=project_configs,
                mode=MigrationMode.PLAN_ONLY,
                parallel_limit=3
            )
            
            assert result["status"] == "partial_success"
            assert result["total_projects"] == 5
            assert result["successful"] == 2  # Projects 2, 4
            assert result["failed"] == 3  # Projects 1, 3, 5
            assert len(result["results"]) == 5
    
    async def test_batch_migration_all_failures(self, batch_orchestrator):
        """Test batch migration where all projects fail"""
        mock_result = {
            "status": "failed",
            "mode": "PLAN_ONLY",
            "error": "Simulated failure"
        }
        
        from app.agents.orchestrator import AgentOrchestrator
        
        with patch.object(
            AgentOrchestrator,
            'run_migration',
            new_callable=AsyncMock,
            return_value=mock_result
        ):
            project_configs = [
                {
                    "project_id": i,
                    "gitlab_url": "https://gitlab.com",
                    "gitlab_token": "test-token",
                    "github_token": "test-github-token",
                    "output_dir": f"/tmp/test/{i}"
                }
                for i in range(1, 4)
            ]
            
            result = await batch_orchestrator.execute_batch_migration(
                project_configs=project_configs,
                mode=MigrationMode.PLAN_ONLY,
                parallel_limit=3
            )
            
            assert result["status"] == "failed"
            assert result["total_projects"] == 3
            assert result["successful"] == 0
            assert result["failed"] == 3
    
    async def test_batch_migration_with_exception(self, batch_orchestrator):
        """Test batch migration handles exceptions gracefully"""
        # Mock to raise exception for one project
        call_count = [0]
        
        async def mock_run_migration(mode, config, resume_from=None):
            call_count[0] += 1
            if call_count[0] == 2:
                raise ValueError("Simulated exception")
            return {
                "status": "success",
                "mode": mode.value,
                "agents": {}
            }
        
        from app.agents.orchestrator import AgentOrchestrator
        
        with patch.object(
            AgentOrchestrator,
            'run_migration',
            new_callable=AsyncMock,
            side_effect=mock_run_migration
        ):
            project_configs = [
                {
                    "project_id": i,
                    "gitlab_url": "https://gitlab.com",
                    "gitlab_token": "test-token",
                    "github_token": "test-github-token",
                    "output_dir": f"/tmp/test/{i}"
                }
                for i in range(1, 4)
            ]
            
            result = await batch_orchestrator.execute_batch_migration(
                project_configs=project_configs,
                mode=MigrationMode.PLAN_ONLY,
                parallel_limit=3
            )
            
            # Should have partial success - 2 successes, 1 exception
            assert result["status"] == "partial_success"
            assert result["successful"] == 2
            assert result["failed"] == 1
    
    async def test_batch_migration_respects_parallel_limit(self, batch_orchestrator):
        """Test that parallel_limit is respected during execution"""
        import asyncio
        
        # Track concurrent executions
        concurrent_count = [0]
        max_concurrent = [0]
        lock = asyncio.Lock()
        
        async def mock_run_migration(mode, config, resume_from=None):
            async with lock:
                concurrent_count[0] += 1
                max_concurrent[0] = max(max_concurrent[0], concurrent_count[0])
            
            # Simulate some work
            await asyncio.sleep(0.1)
            
            async with lock:
                concurrent_count[0] -= 1
            
            return {
                "status": "success",
                "mode": mode.value,
                "agents": {}
            }
        
        from app.agents.orchestrator import AgentOrchestrator
        
        with patch.object(
            AgentOrchestrator,
            'run_migration',
            new_callable=AsyncMock,
            side_effect=mock_run_migration
        ):
            project_configs = [
                {
                    "project_id": i,
                    "gitlab_url": "https://gitlab.com",
                    "gitlab_token": "test-token",
                    "github_token": "test-github-token",
                    "output_dir": f"/tmp/test/{i}"
                }
                for i in range(10)
            ]
            
            result = await batch_orchestrator.execute_batch_migration(
                project_configs=project_configs,
                mode=MigrationMode.PLAN_ONLY,
                parallel_limit=3
            )
            
            assert result["status"] == "success"
            # Verify parallel limit was respected
            assert max_concurrent[0] <= 3
    
    async def test_batch_migration_empty_config_list(self, batch_orchestrator):
        """Test batch migration with empty project list"""
        result = await batch_orchestrator.execute_batch_migration(
            project_configs=[],
            mode=MigrationMode.PLAN_ONLY,
            parallel_limit=5
        )
        
        assert result["status"] == "success"
        assert result["total_projects"] == 0
        assert result["successful"] == 0
        assert result["failed"] == 0
        assert len(result["results"]) == 0
    
    async def test_batch_migration_different_modes(self, batch_orchestrator):
        """Test batch migration with different migration modes"""
        modes = [
            MigrationMode.DISCOVER_ONLY,
            MigrationMode.EXPORT_ONLY,
            MigrationMode.PLAN_ONLY,
            MigrationMode.FULL
        ]
        
        from app.agents.orchestrator import AgentOrchestrator
        
        for mode in modes:
            mock_result = {
                "status": "success",
                "mode": mode.value,
                "agents": {}
            }
            
            with patch.object(
                AgentOrchestrator,
                'run_migration',
                new_callable=AsyncMock,
                return_value=mock_result
            ):
                project_configs = [
                    {
                        "project_id": 1,
                        "gitlab_url": "https://gitlab.com",
                        "gitlab_token": "test-token",
                        "github_token": "test-github-token",
                        "output_dir": "/tmp/test"
                    }
                ]
                
                result = await batch_orchestrator.execute_batch_migration(
                    project_configs=project_configs,
                    mode=mode,
                    parallel_limit=1
                )
                
                assert result["status"] == "success"
                assert result["mode"] == mode.value
