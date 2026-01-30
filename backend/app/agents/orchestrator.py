"""Agent Orchestrator using Microsoft Agent Framework workflow patterns"""

from typing import Any, Dict, List, Optional
from enum import Enum
import asyncio
from datetime import datetime

from app.agents.base_agent import BaseAgent
from app.agents.discovery_agent import DiscoveryAgent
from app.agents.export_agent import ExportAgent
from app.agents.transform_agent import TransformAgent
from app.agents.plan_agent import PlanAgent
from app.agents.apply_agent import ApplyAgent
from app.agents.verify_agent import VerifyAgent
from app.utils.logging import get_logger

logger = get_logger(__name__)


class MigrationMode(str, Enum):
    """Migration run modes"""
    DISCOVER_ONLY = "DISCOVER_ONLY"
    EXPORT_ONLY = "EXPORT_ONLY"
    TRANSFORM_ONLY = "TRANSFORM_ONLY"
    PLAN_ONLY = "PLAN_ONLY"
    DRY_RUN = "DRY_RUN"
    APPLY = "APPLY"
    VERIFY = "VERIFY"
    FULL = "FULL"
    SINGLE_PROJECT = "SINGLE_PROJECT"  # New mode for quick migrate


class AgentOrchestrator:
    """
    Orchestrator for managing multi-agent migration workflows.
    
    Implements Microsoft Agent Framework workflow patterns:
    - Sequential agent execution
    - Conditional routing based on mode
    - State management and context sharing
    - Error handling and resume support
    - Progress tracking and reporting
    
    This orchestrator coordinates specialized agents:
    - DiscoveryAgent: Scan GitLab
    - ExportAgent: Export data
    - TransformAgent: Convert to GitHub format
    - PlanAgent: Generate execution plan
    - ApplyAgent: Execute on GitHub
    - VerifyAgent: Validate results
    """
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.agents = {
            "discovery": DiscoveryAgent(),
            "export": ExportAgent(),
            "transform": TransformAgent(),
            "plan": PlanAgent(),
            "apply": ApplyAgent(),
            "verify": VerifyAgent()
        }
        self.shared_context = {}
    
    async def run_migration(
        self,
        mode: MigrationMode,
        config: Dict[str, Any],
        resume_from: Optional[str] = None,
        stage_callback: Optional[callable] = None,
        complete_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Run migration workflow based on mode.
        
        Args:
            mode: Migration mode determining which agents to run
            config: Configuration for migration
            resume_from: Agent to resume from (if resuming)
            stage_callback: Optional async callback to update stage status
            complete_callback: Optional async callback when stage completes
            
        Returns:
            Dict with results from all executed agents
        """
        self.logger.info(f"Starting migration workflow in {mode} mode")
        
        results = {
            "mode": mode,
            "started_at": datetime.utcnow().isoformat(),
            "agents": {}
        }
        
        try:
            # Determine which agents to run based on mode
            agents_to_run = self._get_agent_sequence(mode, resume_from)
            
            self.logger.info(f"Agent sequence: {agents_to_run}")
            
            # Execute agents sequentially (MAF sequential workflow pattern)
            for agent_name in agents_to_run:
                self.logger.info(f"Executing {agent_name}...")
                
                # Update stage via callback
                if stage_callback:
                    await stage_callback(agent_name)
                
                # Get agent
                agent = self.agents[agent_name]
                
                # Prepare inputs from shared context and config
                inputs = self._prepare_agent_inputs(agent_name, config)
                
                # Execute agent with retry
                result = await agent.run_with_retry(
                    inputs,
                    max_retries=config.get("max_retries", 3),
                    retry_delay=config.get("retry_delay", 5)
                )
                
                # Store result
                results["agents"][agent_name] = result
                
                # Call complete callback
                if complete_callback:
                    await complete_callback(agent_name, result)
                
                # Update shared context for next agent
                if result.get("status") == "success":
                    self._update_shared_context(agent_name, result.get("outputs", {}))
                else:
                    # Agent failed, stop workflow
                    self.logger.error(f"Agent {agent_name} failed, stopping workflow")
                    results["status"] = "failed"
                    results["failed_at_agent"] = agent_name
                    results["finished_at"] = datetime.utcnow().isoformat()
                    return results
            
            # All agents completed successfully
            results["status"] = "success"
            results["finished_at"] = datetime.utcnow().isoformat()
            self.logger.info("Migration workflow completed successfully")
            
        except Exception as e:
            self.logger.error(f"Workflow failed: {str(e)}")
            results["status"] = "failed"
            results["error"] = str(e)
            results["finished_at"] = datetime.utcnow().isoformat()
        
        return results
    
    def _get_agent_sequence(
        self,
        mode: MigrationMode,
        resume_from: Optional[str] = None
    ) -> List[str]:
        """
        Determine agent execution sequence based on mode.
        
        This implements MAF's conditional routing pattern.
        """
        # Full sequence
        full_sequence = [
            "discovery",
            "export",
            "transform",
            "plan",
            "apply",
            "verify"
        ]
        
        # Mode-specific sequences
        sequences = {
            MigrationMode.DISCOVER_ONLY: ["discovery"],
            MigrationMode.EXPORT_ONLY: ["discovery", "export"],
            MigrationMode.TRANSFORM_ONLY: ["discovery", "export", "transform"],
            MigrationMode.PLAN_ONLY: ["discovery", "export", "transform", "plan"],
            MigrationMode.DRY_RUN: ["discovery", "export", "transform", "plan", "apply"],
            MigrationMode.APPLY: ["discovery", "export", "transform", "plan", "apply"],
            MigrationMode.VERIFY: ["verify"],
            MigrationMode.FULL: full_sequence,
            MigrationMode.SINGLE_PROJECT: ["export", "transform", "plan"]  # Skip discovery for single project
        }
        
        sequence = sequences.get(mode, full_sequence)
        
        # Handle resume
        if resume_from and resume_from in sequence:
            resume_index = sequence.index(resume_from)
            sequence = sequence[resume_index:]
        
        return sequence
    
    def _prepare_agent_inputs(
        self,
        agent_name: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepare inputs for an agent from config and shared context.
        
        This implements MAF's context sharing pattern.
        """
        # Base inputs from config
        inputs = config.copy()
        
        # Add shared context data
        inputs.update(self.shared_context)
        
        # Agent-specific input preparation
        if agent_name == "discovery":
            inputs.update({
                "gitlab_url": config.get("gitlab_url"),
                "gitlab_token": config.get("gitlab_token"),
                # Scope configuration
                "scope_type": config.get("scope_type"),  # 'project' or 'group'
                "scope_id": config.get("scope_id"),       # GitLab project/group ID
                "scope_path": config.get("scope_path"),   # Full path
                # Legacy support
                "root_group": config.get("root_group") or (config.get("scope_path") if config.get("scope_type") == "group" else None),
                "output_dir": config.get("output_dir", f"artifacts/runs/{config.get('run_id')}/discovery")
            })
        
        elif agent_name == "export":
            # Extract project_id from discovered projects
            discovered = self.shared_context.get("discovered_projects", [])
            
            # Prepare base inputs with output_dir
            export_inputs = {
                "output_dir": config.get("output_dir", f"artifacts/runs/{config.get('run_id')}/export")
            }
            
            if discovered:
                # Take first project (TODO: support multi-project or user selection)
                first_project = discovered[0]
                export_inputs.update({
                    "project_id": first_project["id"],
                    "gitlab_url": config.get("gitlab_url"),
                    "gitlab_token": config.get("gitlab_token")
                })
            else:
                # Log warning - export agent will fail validation without project_id
                self.logger.warning(
                    "No discovered projects available for export. "
                    "Export agent will fail validation. "
                    "Ensure discovery agent ran successfully first."
                )
            
            inputs.update(export_inputs)
        
        elif agent_name == "transform":
            inputs.update({
                "export_data": self.shared_context.get("export_data"),
                "output_dir": config.get("output_dir", f"artifacts/runs/{config.get('run_id')}/transform")
            })
        
        elif agent_name == "plan":
            # Get project info from discovered projects
            discovered = self.shared_context.get("discovered_projects", [])
            gitlab_project = "namespace/project"
            if discovered:
                gitlab_project = discovered[0].get("path_with_namespace", gitlab_project)
            
            # Build github target from org + repo name
            github_org = config.get("github_org", "org")
            repo_name = gitlab_project.split("/")[-1] if gitlab_project else "repo"
            github_target = f"{github_org}/{repo_name}" if github_org else f"org/{repo_name}"
            
            inputs.update({
                "transform_data": self.shared_context.get("transform_data"),
                "export_data": self.shared_context.get("export_data"),
                "gitlab_project": gitlab_project,
                "github_target": github_target,
                "output_dir": config.get("output_dir", f"artifacts/runs/{config.get('run_id')}/plan"),
                "component_selection": config.get("component_selection")  # Pass component selection from run
            })
        
        elif agent_name == "apply":
            # Check if this is a dry run
            dry_run = config.get("mode") == "DRY_RUN" or config.get("mode") == MigrationMode.DRY_RUN
            inputs.update({
                "github_token": config.get("github_token"),
                "plan": self.shared_context.get("plan"),
                "output_dir": config.get("output_dir", f"artifacts/runs/{config.get('run_id')}/apply"),
                "dry_run": dry_run
            })
        
        elif agent_name == "verify":
            inputs.update({
                "github_token": config.get("github_token"),
                "github_repo": config.get("github_repo"),
                "expected_state": self.shared_context.get("expected_state"),
                "output_dir": config.get("output_dir", f"artifacts/runs/{config.get('run_id')}/verify")
            })
        
        return inputs
    
    def _update_shared_context(self, agent_name: str, outputs: Dict[str, Any]):
        """
        Update shared context with agent outputs.
        
        This enables data flow between agents (MAF context management).
        """
        self.shared_context[f"{agent_name}_outputs"] = outputs
        
        # Extract key data for next agents
        if agent_name == "discovery":
            self.shared_context["discovered_projects"] = outputs.get("discovered_projects", [])
            self.shared_context["inventory"] = outputs.get("inventory")
        
        elif agent_name == "export":
            self.shared_context["export_data"] = outputs
        
        elif agent_name == "transform":
            self.shared_context["transform_data"] = outputs
            self.shared_context["conversion_gaps"] = outputs.get("conversion_gaps", [])
        
        elif agent_name == "plan":
            self.shared_context["plan"] = outputs.get("plan")
            self.shared_context["expected_state"] = outputs.get("expected_state")
        
        elif agent_name == "apply":
            self.shared_context["apply_results"] = outputs
        
        self.logger.debug(f"Updated shared context with {agent_name} outputs")
    
    async def run_parallel_agents(
        self,
        agent_configs: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Run multiple agents in parallel.
        
        This implements MAF's concurrent orchestration pattern.
        Useful for processing multiple projects simultaneously.
        
        Args:
            agent_configs: List of (agent_name, inputs) configs
            
        Returns:
            List of results from all agents
        """
        tasks = []
        
        for config in agent_configs:
            agent_name = config["agent"]
            inputs = config["inputs"]
            agent = self.agents[agent_name]
            
            task = agent.run_with_retry(inputs)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return results
    
    def get_shared_context(self) -> Dict[str, Any]:
        """Get current shared context"""
        return self.shared_context.copy()
    
    def clear_shared_context(self):
        """Clear shared context"""
        self.shared_context = {}
