"""Tests for Agent Orchestrator"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.agents.orchestrator import AgentOrchestrator, MigrationMode


class TestOrchestratorPrepareAgentInputs:
    """Test _prepare_agent_inputs method"""

    def test_prepare_export_inputs_with_discovered_projects(self):
        """Test that export agent receives project_id from discovered projects"""
        # Arrange
        orchestrator = AgentOrchestrator()
        
        # Simulate discovery agent completing with discovered projects
        orchestrator.shared_context = {
            "discovered_projects": [
                {"id": 123, "name": "test-project", "path_with_namespace": "group/test-project"},
                {"id": 456, "name": "another-project", "path_with_namespace": "group/another-project"}
            ]
        }
        
        config = {
            "run_id": "test-run-123",
            "gitlab_url": "https://gitlab.example.com",
            "gitlab_token": "glpat-test-token",
            "output_dir": "artifacts/runs/test-run-123"
        }
        
        # Act
        inputs = orchestrator._prepare_agent_inputs("export", config)
        
        # Assert
        assert "project_id" in inputs, "project_id should be in inputs"
        assert inputs["project_id"] == 123, "project_id should be from first discovered project"
        assert inputs["gitlab_url"] == "https://gitlab.example.com"
        assert inputs["gitlab_token"] == "glpat-test-token"
        assert "output_dir" in inputs, "output_dir should be in inputs"
    
    def test_prepare_export_inputs_without_discovered_projects(self):
        """Test that export agent handles empty discovered projects with warning"""
        # Arrange
        orchestrator = AgentOrchestrator()
        
        # Simulate no discovered projects
        orchestrator.shared_context = {
            "discovered_projects": []
        }
        
        config = {
            "run_id": "test-run-456",
            "gitlab_url": "https://gitlab.example.com",
            "gitlab_token": "glpat-test-token"
        }
        
        # Act
        inputs = orchestrator._prepare_agent_inputs("export", config)
        
        # Assert
        assert "project_id" not in inputs, "project_id should not be set if no projects discovered"
        assert "output_dir" in inputs, "output_dir should still be set"
        # Note: Export agent will fail validation without project_id, which is expected behavior
    
    def test_prepare_discovery_inputs(self):
        """Test that discovery agent receives correct inputs"""
        # Arrange
        orchestrator = AgentOrchestrator()
        
        config = {
            "run_id": "test-run-789",
            "gitlab_url": "https://gitlab.example.com",
            "gitlab_token": "glpat-test-token",
            "root_group": "test-group"
        }
        
        # Act
        inputs = orchestrator._prepare_agent_inputs("discovery", config)
        
        # Assert
        assert inputs["gitlab_url"] == "https://gitlab.example.com"
        assert inputs["gitlab_token"] == "glpat-test-token"
        assert inputs["root_group"] == "test-group"
        assert "artifacts/runs/test-run-789/discovery" in inputs["output_dir"]


class TestOrchestratorUpdateSharedContext:
    """Test _update_shared_context method"""
    
    def test_update_shared_context_after_discovery(self):
        """Test that discovered_projects are added to shared context"""
        # Arrange
        orchestrator = AgentOrchestrator()
        
        discovery_outputs = {
            "discovered_projects": [
                {"id": 123, "name": "test-project"},
                {"id": 456, "name": "another-project"}
            ],
            "inventory": {"version": "2.0"},
            "stats": {"projects": 2}
        }
        
        # Act
        orchestrator._update_shared_context("discovery", discovery_outputs)
        
        # Assert
        assert "discovered_projects" in orchestrator.shared_context
        assert len(orchestrator.shared_context["discovered_projects"]) == 2
        assert orchestrator.shared_context["discovered_projects"][0]["id"] == 123
        assert "inventory" in orchestrator.shared_context


@pytest.mark.asyncio
class TestOrchestratorIntegration:
    """Integration tests for orchestrator workflow"""
    
    async def test_discovery_to_export_flow(self):
        """Test that project_id flows from discovery to export agent"""
        # Arrange
        orchestrator = AgentOrchestrator()
        
        # Mock discovery agent to return discovered projects
        mock_discovery_result = {
            "status": "success",
            "outputs": {
                "discovered_projects": [
                    {"id": 999, "name": "integration-test-project"}
                ],
                "inventory": {},
                "stats": {"projects": 1}
            }
        }
        
        # Mock export agent
        mock_export_result = {
            "status": "success",
            "outputs": {}
        }
        
        with patch.object(orchestrator.agents["discovery"], "run_with_retry", new=AsyncMock(return_value=mock_discovery_result)):
            with patch.object(orchestrator.agents["export"], "run_with_retry", new=AsyncMock(return_value=mock_export_result)) as mock_export:
                config = {
                    "run_id": "integration-test",
                    "gitlab_url": "https://gitlab.example.com",
                    "gitlab_token": "test-token"
                }
                
                # Act
                result = await orchestrator.run_migration(
                    mode=MigrationMode.EXPORT_ONLY,
                    config=config
                )
                
                # Assert
                assert result["status"] == "success"
                
                # Check that export agent was called with project_id
                mock_export.assert_called_once()
                export_call_args = mock_export.call_args[0][0]
                assert "project_id" in export_call_args, "Export agent should receive project_id"
                assert export_call_args["project_id"] == 999, "project_id should match discovered project"
