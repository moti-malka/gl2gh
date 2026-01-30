"""Unit and Integration tests for Agent Orchestrator"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from app.agents.orchestrator import AgentOrchestrator, MigrationMode


@pytest.fixture
def orchestrator():
    """Create AgentOrchestrator instance"""
    return AgentOrchestrator()


@pytest.fixture
def basic_config():
    """Basic configuration for testing"""
    return {
        "run_id": "test-run-001",
        "gitlab_url": "https://gitlab.com",
        "gitlab_token": "glpat-test-token",
        "github_token": "ghp_test-token",
        "root_group": "test-group",
        "github_repo": "org/repo",
        "output_dir": "/tmp/test-migration"
    }


@pytest.fixture
def mock_agent_success():
    """Mock agent that returns success"""
    async def run_with_retry(inputs, max_retries=3, retry_delay=5):
        return {
            "status": "success",
            "outputs": {
                "test_data": "test_value",
                "artifacts": []
            },
            "errors": []
        }
    
    agent = Mock()
    agent.run_with_retry = run_with_retry
    return agent


@pytest.fixture
def mock_agent_failure():
    """Mock agent that returns failure"""
    async def run_with_retry(inputs, max_retries=3, retry_delay=5):
        return {
            "status": "failed",
            "outputs": {},
            "errors": [{"message": "Agent failed"}]
        }
    
    agent = Mock()
    agent.run_with_retry = run_with_retry
    return agent


@pytest.mark.asyncio
class TestAgentOrchestrator:
    """Test cases for AgentOrchestrator"""
    
    async def test_initialization(self, orchestrator):
        """Test orchestrator initialization"""
        assert orchestrator.agents is not None
        assert len(orchestrator.agents) == 6
        assert "discovery" in orchestrator.agents
        assert "export" in orchestrator.agents
        assert "transform" in orchestrator.agents
        assert "plan" in orchestrator.agents
        assert "apply" in orchestrator.agents
        assert "verify" in orchestrator.agents
        assert orchestrator.shared_context == {}
    
    async def test_get_agent_sequence_discover_only(self, orchestrator):
        """Test agent sequence for DISCOVER_ONLY mode"""
        sequence = orchestrator._get_agent_sequence(MigrationMode.DISCOVER_ONLY)
        assert sequence == ["discovery"]
    
    async def test_get_agent_sequence_export_only(self, orchestrator):
        """Test agent sequence for EXPORT_ONLY mode"""
        sequence = orchestrator._get_agent_sequence(MigrationMode.EXPORT_ONLY)
        assert sequence == ["discovery", "export"]
    
    async def test_get_agent_sequence_transform_only(self, orchestrator):
        """Test agent sequence for TRANSFORM_ONLY mode"""
        sequence = orchestrator._get_agent_sequence(MigrationMode.TRANSFORM_ONLY)
        assert sequence == ["discovery", "export", "transform"]
    
    async def test_get_agent_sequence_plan_only(self, orchestrator):
        """Test agent sequence for PLAN_ONLY mode"""
        sequence = orchestrator._get_agent_sequence(MigrationMode.PLAN_ONLY)
        assert sequence == ["discovery", "export", "transform", "plan"]
    
    async def test_get_agent_sequence_apply(self, orchestrator):
        """Test agent sequence for APPLY mode"""
        sequence = orchestrator._get_agent_sequence(MigrationMode.APPLY)
        assert sequence == ["discovery", "export", "transform", "plan", "apply"]
    
    async def test_get_agent_sequence_verify(self, orchestrator):
        """Test agent sequence for VERIFY mode"""
        sequence = orchestrator._get_agent_sequence(MigrationMode.VERIFY)
        assert sequence == ["verify"]
    
    async def test_get_agent_sequence_full(self, orchestrator):
        """Test agent sequence for FULL mode"""
        sequence = orchestrator._get_agent_sequence(MigrationMode.FULL)
        assert sequence == ["discovery", "export", "transform", "plan", "apply", "verify"]
    
    async def test_get_agent_sequence_with_resume(self, orchestrator):
        """Test agent sequence with resume from specific agent"""
        sequence = orchestrator._get_agent_sequence(
            MigrationMode.FULL,
            resume_from="transform"
        )
        assert sequence == ["transform", "plan", "apply", "verify"]
        assert "discovery" not in sequence
        assert "export" not in sequence
    
    async def test_prepare_agent_inputs_discovery(self, orchestrator, basic_config):
        """Test input preparation for discovery agent"""
        inputs = orchestrator._prepare_agent_inputs("discovery", basic_config)
        
        assert "gitlab_url" in inputs
        assert "gitlab_token" in inputs
        assert "root_group" in inputs
        assert "output_dir" in inputs
        assert inputs["gitlab_url"] == basic_config["gitlab_url"]
    
    async def test_prepare_agent_inputs_export(self, orchestrator, basic_config):
        """Test input preparation for export agent"""
        inputs = orchestrator._prepare_agent_inputs("export", basic_config)
        
        assert "output_dir" in inputs
        assert "run_id" in inputs
    
    async def test_prepare_agent_inputs_transform(self, orchestrator, basic_config):
        """Test input preparation for transform agent"""
        # Add data to shared context
        orchestrator.shared_context["export_data"] = {"test": "data"}
        
        inputs = orchestrator._prepare_agent_inputs("transform", basic_config)
        
        assert "export_data" in inputs
        assert "output_dir" in inputs
        assert inputs["export_data"] == {"test": "data"}
    
    async def test_prepare_agent_inputs_plan(self, orchestrator, basic_config):
        """Test input preparation for plan agent"""
        orchestrator.shared_context["transform_data"] = {"test": "data"}
        
        inputs = orchestrator._prepare_agent_inputs("plan", basic_config)
        
        assert "transform_data" in inputs
        assert "output_dir" in inputs
    
    async def test_prepare_agent_inputs_apply(self, orchestrator, basic_config):
        """Test input preparation for apply agent"""
        orchestrator.shared_context["plan"] = {"actions": []}
        
        inputs = orchestrator._prepare_agent_inputs("apply", basic_config)
        
        assert "github_token" in inputs
        assert "plan" in inputs
        assert "output_dir" in inputs
    
    async def test_prepare_agent_inputs_verify(self, orchestrator, basic_config):
        """Test input preparation for verify agent"""
        orchestrator.shared_context["expected_state"] = {"repos": 1}
        
        inputs = orchestrator._prepare_agent_inputs("verify", basic_config)
        
        assert "github_token" in inputs
        assert "github_repo" in inputs
        assert "expected_state" in inputs
        assert "output_dir" in inputs
    
    async def test_update_shared_context_discovery(self, orchestrator):
        """Test shared context update for discovery agent"""
        outputs = {
            "discovered_projects": [{"id": 1, "name": "project1"}],
            "inventory": {"total": 1}
        }
        
        orchestrator._update_shared_context("discovery", outputs)
        
        assert "discovery_outputs" in orchestrator.shared_context
        assert "discovered_projects" in orchestrator.shared_context
        assert "inventory" in orchestrator.shared_context
        assert len(orchestrator.shared_context["discovered_projects"]) == 1
    
    async def test_update_shared_context_export(self, orchestrator):
        """Test shared context update for export agent"""
        outputs = {
            "project_id": 123,
            "export_stats": {"issues": 10}
        }
        
        orchestrator._update_shared_context("export", outputs)
        
        assert "export_outputs" in orchestrator.shared_context
        assert "export_data" in orchestrator.shared_context
        assert orchestrator.shared_context["export_data"]["project_id"] == 123
    
    async def test_update_shared_context_transform(self, orchestrator):
        """Test shared context update for transform agent"""
        outputs = {
            "transform_complete": True,
            "conversion_gaps": [{"feature": "include"}]
        }
        
        orchestrator._update_shared_context("transform", outputs)
        
        assert "transform_outputs" in orchestrator.shared_context
        assert "transform_data" in orchestrator.shared_context
        assert "conversion_gaps" in orchestrator.shared_context
        assert len(orchestrator.shared_context["conversion_gaps"]) == 1
    
    async def test_update_shared_context_plan(self, orchestrator):
        """Test shared context update for plan agent"""
        outputs = {
            "plan": {"actions": []},
            "expected_state": {"repos": 1}
        }
        
        orchestrator._update_shared_context("plan", outputs)
        
        assert "plan_outputs" in orchestrator.shared_context
        assert "plan" in orchestrator.shared_context
        assert "expected_state" in orchestrator.shared_context
    
    async def test_update_shared_context_apply(self, orchestrator):
        """Test shared context update for apply agent"""
        outputs = {
            "actions_executed": 10,
            "results": []
        }
        
        orchestrator._update_shared_context("apply", outputs)
        
        assert "apply_outputs" in orchestrator.shared_context
        assert "apply_results" in orchestrator.shared_context
    
    async def test_run_migration_discover_only(self, orchestrator, basic_config, mock_agent_success):
        """Test running migration in DISCOVER_ONLY mode"""
        # Mock the discovery agent
        orchestrator.agents["discovery"] = mock_agent_success
        
        result = await orchestrator.run_migration(
            mode=MigrationMode.DISCOVER_ONLY,
            config=basic_config
        )
        
        assert result["mode"] == MigrationMode.DISCOVER_ONLY
        assert result["status"] == "success"
        assert "discovery" in result["agents"]
        assert "export" not in result["agents"]
        assert "started_at" in result
        assert "finished_at" in result
    
    async def test_run_migration_full_mode(self, orchestrator, basic_config, mock_agent_success):
        """Test running migration in FULL mode"""
        # Mock all agents
        for agent_name in orchestrator.agents:
            orchestrator.agents[agent_name] = mock_agent_success
        
        result = await orchestrator.run_migration(
            mode=MigrationMode.FULL,
            config=basic_config
        )
        
        assert result["mode"] == MigrationMode.FULL
        assert result["status"] == "success"
        assert len(result["agents"]) == 6
        assert "discovery" in result["agents"]
        assert "export" in result["agents"]
        assert "transform" in result["agents"]
        assert "plan" in result["agents"]
        assert "apply" in result["agents"]
        assert "verify" in result["agents"]
    
    async def test_run_migration_with_agent_failure(self, orchestrator, basic_config, mock_agent_success, mock_agent_failure):
        """Test migration workflow stops on agent failure"""
        # First agent succeeds, second fails
        orchestrator.agents["discovery"] = mock_agent_success
        orchestrator.agents["export"] = mock_agent_failure
        orchestrator.agents["transform"] = mock_agent_success
        
        result = await orchestrator.run_migration(
            mode=MigrationMode.TRANSFORM_ONLY,
            config=basic_config
        )
        
        assert result["status"] == "failed"
        assert "failed_at_agent" in result
        assert result["failed_at_agent"] == "export"
        # Should have executed discovery and export only
        assert "discovery" in result["agents"]
        assert "export" in result["agents"]
        # Should not have executed transform
        assert "transform" not in result["agents"]
    
    async def test_run_migration_with_resume(self, orchestrator, basic_config, mock_agent_success):
        """Test resuming migration from specific agent"""
        # Mock agents
        for agent_name in orchestrator.agents:
            orchestrator.agents[agent_name] = mock_agent_success
        
        result = await orchestrator.run_migration(
            mode=MigrationMode.FULL,
            config=basic_config,
            resume_from="plan"
        )
        
        assert result["status"] == "success"
        # Should only execute from plan onwards
        assert "plan" in result["agents"]
        assert "apply" in result["agents"]
        assert "verify" in result["agents"]
        # Should not execute earlier agents
        assert "discovery" not in result["agents"]
        assert "export" not in result["agents"]
        assert "transform" not in result["agents"]
    
    async def test_run_migration_context_sharing(self, orchestrator, basic_config):
        """Test context is shared between agents"""
        # Create mock agents that check for context
        async def discovery_run(inputs, max_retries=3, retry_delay=5):
            return {
                "status": "success",
                "outputs": {
                    "discovered_projects": [{"id": 1}]
                },
                "errors": []
            }
        
        async def export_run(inputs, max_retries=3, retry_delay=5):
            # Check that discovery outputs are available
            assert "discovered_projects" in inputs
            return {
                "status": "success",
                "outputs": {
                    "export_data": {"test": "data"}
                },
                "errors": []
            }
        
        discovery_agent = Mock()
        discovery_agent.run_with_retry = discovery_run
        
        export_agent = Mock()
        export_agent.run_with_retry = export_run
        
        orchestrator.agents["discovery"] = discovery_agent
        orchestrator.agents["export"] = export_agent
        
        result = await orchestrator.run_migration(
            mode=MigrationMode.EXPORT_ONLY,
            config=basic_config
        )
        
        assert result["status"] == "success"
        assert "discovered_projects" in orchestrator.shared_context
        assert "export_data" in orchestrator.shared_context
    
    async def test_run_migration_exception_handling(self, orchestrator, basic_config):
        """Test exception handling during migration"""
        # Create agent that raises exception
        async def failing_run(inputs, max_retries=3, retry_delay=5):
            raise Exception("Unexpected error")
        
        failing_agent = Mock()
        failing_agent.run_with_retry = failing_run
        
        orchestrator.agents["discovery"] = failing_agent
        
        result = await orchestrator.run_migration(
            mode=MigrationMode.DISCOVER_ONLY,
            config=basic_config
        )
        
        assert result["status"] == "failed"
        assert "error" in result
        assert "Unexpected error" in result["error"]
    
    async def test_run_parallel_agents(self, orchestrator, mock_agent_success):
        """Test running agents in parallel"""
        agent_configs = [
            {
                "agent": "discovery",
                "inputs": {"gitlab_url": "https://gitlab.com", "gitlab_token": "token1"}
            },
            {
                "agent": "discovery",
                "inputs": {"gitlab_url": "https://gitlab.com", "gitlab_token": "token2"}
            }
        ]
        
        # Mock the discovery agent
        orchestrator.agents["discovery"] = mock_agent_success
        
        results = await orchestrator.run_parallel_agents(agent_configs)
        
        assert len(results) == 2
        assert all(r["status"] == "success" for r in results if isinstance(r, dict))
    
    async def test_run_parallel_agents_with_failures(self, orchestrator, mock_agent_success, mock_agent_failure):
        """Test parallel agents with some failures"""
        agent_configs = [
            {
                "agent": "discovery",
                "inputs": {"test": "input1"}
            },
            {
                "agent": "export",
                "inputs": {"test": "input2"}
            }
        ]
        
        orchestrator.agents["discovery"] = mock_agent_success
        orchestrator.agents["export"] = mock_agent_failure
        
        results = await orchestrator.run_parallel_agents(agent_configs)
        
        assert len(results) == 2
        # First should succeed, second should fail
        assert results[0]["status"] == "success"
        assert results[1]["status"] == "failed"
    
    async def test_get_shared_context(self, orchestrator):
        """Test getting shared context"""
        orchestrator.shared_context = {
            "test_key": "test_value",
            "nested": {"data": "value"}
        }
        
        context = orchestrator.get_shared_context()
        
        assert context == orchestrator.shared_context
        # Should be a copy
        context["new_key"] = "new_value"
        assert "new_key" not in orchestrator.shared_context
    
    async def test_clear_shared_context(self, orchestrator):
        """Test clearing shared context"""
        orchestrator.shared_context = {
            "test_key": "test_value",
            "data": {"nested": "value"}
        }
        
        orchestrator.clear_shared_context()
        
        assert orchestrator.shared_context == {}
    
    async def test_full_migration_integration(self, orchestrator, basic_config):
        """Integration test: Full migration flow with realistic mock data"""
        # Create realistic mock agents
        async def discovery_run(inputs, max_retries=3, retry_delay=5):
            return {
                "status": "success",
                "outputs": {
                    "discovered_projects": [
                        {"id": 123, "path": "namespace/project"}
                    ],
                    "inventory": {"total_projects": 1}
                },
                "errors": []
            }
        
        async def export_run(inputs, max_retries=3, retry_delay=5):
            assert "discovered_projects" in inputs
            return {
                "status": "success",
                "outputs": {
                    "project_id": 123,
                    "export_stats": {"issues": 10, "mrs": 5},
                    "gitlab_ci_yaml": {"stages": ["build"]},
                    "issues": [],
                    "merge_requests": []
                },
                "errors": []
            }
        
        async def transform_run(inputs, max_retries=3, retry_delay=5):
            assert "export_data" in inputs
            return {
                "status": "success",
                "outputs": {
                    "transform_complete": True,
                    "workflows_count": 1,
                    "conversion_gaps": []
                },
                "errors": []
            }
        
        async def plan_run(inputs, max_retries=3, retry_delay=5):
            assert "transform_data" in inputs
            return {
                "status": "success",
                "outputs": {
                    "plan": {"actions": [{"id": "action-001"}]},
                    "expected_state": {"repos": 1}
                },
                "errors": []
            }
        
        async def apply_run(inputs, max_retries=3, retry_delay=5):
            assert "plan" in inputs
            return {
                "status": "success",
                "outputs": {
                    "actions_executed": 1,
                    "results": [{"id": "action-001", "status": "success"}]
                },
                "errors": []
            }
        
        async def verify_run(inputs, max_retries=3, retry_delay=5):
            assert "expected_state" in inputs
            return {
                "status": "success",
                "outputs": {
                    "verification_complete": True,
                    "checks_passed": 10,
                    "checks_failed": 0
                },
                "errors": []
            }
        
        # Set up mock agents
        orchestrator.agents["discovery"].run_with_retry = discovery_run
        orchestrator.agents["export"].run_with_retry = export_run
        orchestrator.agents["transform"].run_with_retry = transform_run
        orchestrator.agents["plan"].run_with_retry = plan_run
        orchestrator.agents["apply"].run_with_retry = apply_run
        orchestrator.agents["verify"].run_with_retry = verify_run
        
        # Run full migration
        result = await orchestrator.run_migration(
            mode=MigrationMode.FULL,
            config=basic_config
        )
        
        # Verify results
        assert result["status"] == "success"
        assert len(result["agents"]) == 6
        
        # Check each agent executed successfully
        for agent_name in ["discovery", "export", "transform", "plan", "apply", "verify"]:
            assert agent_name in result["agents"]
            assert result["agents"][agent_name]["status"] == "success"
        
        # Verify context was built up correctly
        assert "discovery_outputs" in orchestrator.shared_context
        assert "export_data" in orchestrator.shared_context
        assert "transform_data" in orchestrator.shared_context
        assert "plan" in orchestrator.shared_context
        assert "apply_results" in orchestrator.shared_context
        
        # Verify data flow
        assert orchestrator.shared_context["discovered_projects"][0]["id"] == 123
        assert orchestrator.shared_context["export_data"]["project_id"] == 123
        assert orchestrator.shared_context["plan"]["actions"][0]["id"] == "action-001"
