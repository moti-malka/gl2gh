"""Discovery Agent - GitLab project discovery and analysis using Microsoft Agent Framework"""

from typing import Any, Dict
import json
import os
from pathlib import Path
from app.agents.base_agent import BaseAgent, AgentResult
from app.utils.logging import get_logger

logger = get_logger(__name__)


class DiscoveryAgent(BaseAgent):
    """
    Discovery Agent for GitLab project scanning and readiness assessment.
    
    This agent uses Microsoft Agent Framework patterns to:
    - Scan GitLab groups and projects
    - Build comprehensive inventory
    - Assess migration readiness
    - Generate detailed reports
    
    Following MAF principles:
    - Clear input/output contracts
    - Deterministic behavior
    - Context awareness
    - Tool integration (GitLab API)
    - Robust error handling
    """
    
    def __init__(self):
        super().__init__(
            agent_name="DiscoveryAgent",
            instructions="""
            You are a specialized agent for discovering and analyzing GitLab projects.
            Your role is to:
            1. Scan GitLab groups and projects comprehensively
            2. Collect detailed facts about each project (CI, LFS, issues, MRs, etc.)
            3. Assess migration readiness and complexity
            4. Identify potential blockers
            5. Generate inventory and readiness reports
            
            Operate in read-only mode - make no changes to GitLab.
            Respect API rate limits and budgets.
            Handle errors gracefully and report partial results.
            """
        )
    
    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        """
        Validate discovery agent inputs.
        
        Required inputs:
            - gitlab_url: GitLab instance URL
            - gitlab_token: Personal Access Token
            - output_dir: Directory for artifacts
            
        Optional inputs:
            - root_group: Root group to scan (None = scan all accessible)
            - max_api_calls: API budget
            - max_per_project_calls: Per-project API budget
            - deep: Enable deep analysis
            - deep_top_n: Limit deep analysis to top N projects
        """
        required_fields = ["gitlab_url", "gitlab_token", "output_dir"]
        
        for field in required_fields:
            if field not in inputs:
                self.log_event("ERROR", f"Missing required input: {field}")
                return False
        
        # Validate URL format
        gitlab_url = inputs["gitlab_url"]
        if not (gitlab_url.startswith("http://") or gitlab_url.startswith("https://")):
            self.log_event("ERROR", f"Invalid GitLab URL format: {gitlab_url}")
            return False
        
        # Validate token format (basic check)
        gitlab_token = inputs["gitlab_token"]
        if not gitlab_token or len(gitlab_token) < 10:
            self.log_event("ERROR", "Invalid GitLab token")
            return False
        
        return True
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute discovery process.
        
        This integrates with the existing discovery_agent module.
        In future iterations, this can be enhanced with MAF's:
        - ChatAgent for intelligent decision-making
        - Function calling for tool integration
        - Memory providers for context management
        """
        self.log_event("INFO", "Starting GitLab discovery")
        
        try:
            # Update context
            self.update_context("run_started", True)
            self.update_context("gitlab_url", inputs["gitlab_url"])
            
            # Import and use existing discovery agent
            # This is where we integrate with the existing discovery_agent module
            from discovery_agent.orchestrator import run_discovery
            
            # Prepare arguments for existing discovery agent
            discovery_args = {
                "base_url": inputs["gitlab_url"],
                "token": inputs["gitlab_token"],
                "root_group": inputs.get("root_group"),
                "output_dir": inputs["output_dir"],
                "max_api_calls": inputs.get("max_api_calls", 5000),
                "max_per_project_calls": inputs.get("max_per_project_calls", 200),
                "deep": inputs.get("deep", False),
                "deep_top_n": inputs.get("deep_top_n", 20)
            }
            
            self.log_event("INFO", "Running discovery with existing discovery_agent module", 
                         {"root_group": discovery_args["root_group"], 
                          "deep": discovery_args["deep"]})
            
            # Run discovery (synchronous call wrapped in async)
            result = await self._run_discovery_sync(discovery_args)
            
            # Generate artifacts
            artifacts = self.generate_artifacts(result)
            
            # Extract statistics
            stats = result.get("run", {}).get("stats", {})
            
            self.log_event("INFO", "Discovery completed successfully", 
                         {"projects": stats.get("projects", 0), 
                          "groups": stats.get("groups", 0),
                          "errors": stats.get("errors", 0)})
            
            return AgentResult(
                status="success",
                outputs={
                    "inventory": result,
                    "stats": stats,
                    "discovered_projects": result.get("projects", []),
                    "discovered_groups": result.get("groups", [])
                },
                artifacts=list(artifacts.values()),
                errors=[]
            ).to_dict()
            
        except Exception as e:
            self.log_event("ERROR", f"Discovery failed: {str(e)}")
            return AgentResult(
                status="failed",
                outputs={},
                artifacts=[],
                errors=[{"step": "discovery", "message": str(e)}]
            ).to_dict()
    
    async def _run_discovery_sync(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run synchronous discovery agent in async context.
        
        This wraps the existing discovery agent's synchronous execution.
        """
        import asyncio
        from functools import partial
        
        # Import after path is set
        from discovery_agent.orchestrator import run_discovery
        
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        func = partial(
            run_discovery,
            base_url=args["base_url"],
            token=args["token"],
            root_group=args.get("root_group"),
            output_dir=args["output_dir"],
            max_api_calls=args["max_api_calls"],
            max_per_project_calls=args["max_per_project_calls"],
            deep=args["deep"],
            deep_top_n=args["deep_top_n"]
        )
        
        result = await loop.run_in_executor(None, func)
        return result
    
    def generate_artifacts(self, data: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate discovery artifacts.
        
        Returns:
            Dict mapping artifact names to paths:
                - inventory: inventory.json
                - summary: summary.txt
                - coverage: coverage.json (if available)
        """
        artifacts = {}
        
        # inventory.json is generated by existing discovery agent
        output_dir = self.get_context("output_dir")
        if output_dir:
            inventory_path = Path(output_dir) / "inventory.json"
            if inventory_path.exists():
                artifacts["inventory"] = str(inventory_path)
            
            summary_path = Path(output_dir) / "summary.txt"
            if summary_path.exists():
                artifacts["summary"] = str(summary_path)
        
        return artifacts
    
    def assess_readiness(self, project: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess migration readiness for a project.
        
        This can be enhanced with MAF's ChatAgent to provide
        intelligent, context-aware readiness assessment.
        
        Args:
            project: Project data
            
        Returns:
            Readiness assessment with blockers and recommendations
        """
        blockers = []
        notes = []
        complexity = "low"
        
        # Check for CI/CD
        if project.get("facts", {}).get("has_ci"):
            blockers.append("Has GitLab CI/CD pipeline - requires conversion to GitHub Actions")
            complexity = "medium"
        
        # Check for LFS
        if project.get("facts", {}).get("has_lfs"):
            notes.append("Uses Git LFS - ensure GitHub LFS is configured")
            if complexity == "low":
                complexity = "medium"
        
        # Check for high activity
        facts = project.get("facts", {})
        if isinstance(facts.get("mr_counts"), dict):
            total_mrs = facts["mr_counts"].get("total", 0)
            if total_mrs > 100:
                complexity = "high"
                notes.append(f"High MR activity ({total_mrs} total) - review migration strategy")
        
        # Check if archived
        if project.get("archived"):
            notes.append("Project is archived - consider excluding from migration")
            complexity = "low"
        
        return {
            "complexity": complexity,
            "blockers": blockers,
            "notes": notes
        }
