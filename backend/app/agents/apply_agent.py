"""Apply Agent - Execute migration plan on GitHub using Microsoft Agent Framework"""

from typing import Any, Dict, List, Optional
from pathlib import Path
import json
import asyncio
from datetime import datetime

from app.agents.base_agent import BaseAgent, AgentResult
from app.agents.actions import ACTION_REGISTRY, ActionResult
from app.clients.github_client import GitHubClient
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ApplyAgent(BaseAgent):
    """
    Apply Agent for executing migration plans on GitHub.
    
    Using Microsoft Agent Framework patterns:
    - Tool integration (GitHub API)
    - Idempotent operations
    - Transactional execution with rollback capability
    - Progress tracking and reporting
    """
    
    def __init__(self):
        super().__init__(
            agent_name="ApplyAgent",
            instructions="""
            You are specialized in executing migration operations on GitHub.
            Your responsibilities:
            1. Execute migration plan actions in order
            2. Create GitHub repositories
            3. Push code and workflows
            4. Create issues and pull requests
            5. Set up environments and secrets
            6. Configure branch protections
            7. Create releases and webhooks
            
            Use idempotency keys to prevent duplicates.
            Handle errors gracefully and support resume.
            Generate comprehensive apply reports.
            """
        )
        self.github_client: Optional[GitHubClient] = None
        self.execution_context: Dict[str, Any] = {}
        self.executed_actions: List[Dict[str, Any]] = []  # Track for rollback
    
    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        """Validate apply inputs"""
        required = ["github_token", "plan", "output_dir"]
        if not all(field in inputs for field in required):
            return False
        
        # Validate plan structure
        plan = inputs["plan"]
        if not isinstance(plan, dict):
            self.log_event("ERROR", "Plan must be a dictionary")
            return False
        
        if "actions" not in plan or not isinstance(plan["actions"], list):
            self.log_event("ERROR", "Plan must contain 'actions' list")
            return False
        
        return True
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute apply process"""
        self.log_event("INFO", "Starting apply execution")
        
        # Check if this is a dry run
        dry_run = inputs.get("dry_run", False)
        if dry_run:
            self.log_event("INFO", "Running in DRY RUN mode - no changes will be made")
        
        try:
            output_dir = Path(inputs["output_dir"])
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize GitHub client
            github_token = inputs["github_token"]
            self.github_client = GitHubClient(
                token=github_token,
                timeout=inputs.get("timeout", 30)
            )
            
            # Initialize execution context
            self.execution_context = {
                "github_token": github_token,
                "output_dir": str(output_dir),
                "id_mappings": {},
                "executed_actions": {},
                "resume_state": inputs.get("resume_state", {}),
                "dry_run": dry_run
            }
            
            # Get plan
            plan = inputs["plan"]
            actions = plan.get("actions", [])
            
            # Check if resuming from previous run
            resume_from = inputs.get("resume_from_action_id")
            if resume_from:
                self.log_event("INFO", f"Resuming from action: {resume_from}")
            
            # Execute actions
            results = await self._execute_actions(actions, resume_from)
            
            # Generate reports
            if dry_run:
                apply_report = self._generate_dry_run_report(plan, results)
            else:
                apply_report = self._generate_apply_report(plan, results)
            
            id_mappings = self.execution_context.get("id_mappings", {})
            errors = [r for r in results if not r.success]
            
            # Save artifacts
            self._save_artifact(output_dir / "apply_report.json", apply_report)
            self._save_artifact(output_dir / "id_mappings.json", id_mappings)
            self._save_artifact(output_dir / "executed_actions.json", {
                "executed_actions": self.executed_actions,
                "timestamp": datetime.utcnow().isoformat()
            })
            if errors:
                self._save_artifact(
                    output_dir / "errors.json", 
                    {"errors": [e.to_dict() for e in errors]}
                )
            
            # Determine overall status
            total_actions = len(actions)
            successful_actions = sum(1 for r in results if r.success)
            
            if successful_actions == total_actions:
                status = "success"
            elif successful_actions > 0:
                status = "partial"
            else:
                status = "failed"
            
            mode_text = "Dry run" if dry_run else "Apply"
            self.log_event("INFO", f"{mode_text} completed: {successful_actions}/{total_actions} actions succeeded")
            
            outputs = {
                "apply_complete": status in ["success", "partial"],
                "actions_executed": successful_actions,
                "actions_total": total_actions,
                "errors": len(errors),
                "dry_run": dry_run
            }
            
            if not dry_run:
                outputs["id_mappings"] = id_mappings
            
            artifacts = [str(output_dir / report_filename)]
            if not dry_run:
                artifacts.append(str(output_dir / "id_mappings.json"))
            
            return AgentResult(
                status=status,
                outputs=outputs,
                artifacts=artifacts,
                errors=[e.to_dict() for e in errors]
            ).to_dict()
            
        except Exception as e:
            self.log_event("ERROR", f"Apply failed: {str(e)}")
            return AgentResult(
                status="failed",
                outputs={},
                artifacts=[],
                errors=[{"step": "apply", "message": str(e)}]
            ).to_dict()
    
    async def _execute_actions(
        self, 
        actions: List[Dict[str, Any]], 
        resume_from: Optional[str] = None
    ) -> List[ActionResult]:
        """
        Execute actions in order with dependency resolution.
        
        Args:
            actions: List of action configurations
            resume_from: Action ID to resume from (None = start from beginning)
            
        Returns:
            List of ActionResult objects
        """
        results: List[ActionResult] = []
        skipping = resume_from is not None
        
        for action_config in actions:
            action_id = action_config.get("id")
            action_type = action_config.get("type")
            
            # Skip until we reach resume point
            if skipping:
                if action_id == resume_from:
                    skipping = False
                else:
                    self.log_event("INFO", f"Skipping action {action_id} (resuming)")
                    continue
            
            # Check dependencies
            dependencies = action_config.get("dependencies", [])
            if not self._check_dependencies(dependencies, results):
                error_msg = f"Dependencies not met for action {action_id}"
                self.log_event("ERROR", error_msg)
                results.append(ActionResult(
                    success=False,
                    action_id=action_id,
                    action_type=action_type,
                    outputs={},
                    error=error_msg
                ))
                continue
            
            # Get action executor class
            action_class = ACTION_REGISTRY.get(action_type)
            if not action_class:
                error_msg = f"Unknown action type: {action_type}"
                self.log_event("ERROR", error_msg)
                results.append(ActionResult(
                    success=False,
                    action_id=action_id,
                    action_type=action_type,
                    outputs={},
                    error=error_msg
                ))
                continue
            
            # Create and execute action
            try:
                action_executor = action_class(
                    action_config=action_config,
                    github_client=self.github_client,
                    context=self.execution_context
                )
                
                # Handle rate limiting (skip in dry-run mode)
                dry_run = self.execution_context.get("dry_run", False)
                if not dry_run:
                    await self._check_rate_limit()
                
                # Execute with retry (or simulate if dry_run)
                result = await action_executor.execute_with_retry(
                    max_retries=3,
                    base_delay=1.0,
                    dry_run=dry_run
                )
                results.append(result)
                
                # Track successful actions for potential rollback
                if result.success and result.rollback_data:
                    self.executed_actions.append({
                        "action_id": action_id,
                        "action_type": action_type,
                        "action_config": action_config,
                        "rollback_data": result.rollback_data,
                        "reversible": result.reversible,
                        "timestamp": result.timestamp.isoformat() if result.timestamp else None
                    })
                
                # Emit progress event
                mode_text = "simulated" if dry_run else ("completed" if result.success else "failed")
                self.log_event(
                    "INFO" if result.success else "ERROR",
                    f"Action {action_id} {mode_text}",
                    {"action_type": action_type, "outputs": result.outputs}
                )
                
            except Exception as e:
                error_msg = f"Exception executing action {action_id}: {str(e)}"
                self.log_event("ERROR", error_msg)
                results.append(ActionResult(
                    success=False,
                    action_id=action_id,
                    action_type=action_type,
                    outputs={},
                    error=error_msg
                ))
        
        return results
    
    def _check_dependencies(
        self, 
        dependencies: List[str], 
        results: List[ActionResult]
    ) -> bool:
        """Check if all dependencies are satisfied"""
        if not dependencies:
            return True
        
        completed_action_ids = {r.action_id for r in results if r.success}
        return all(dep in completed_action_ids for dep in dependencies)
    
    async def _check_rate_limit(self):
        """Check GitHub API rate limit and wait if needed"""
        try:
            rate_limit = await self.github_client.get_rate_limit()
            remaining = rate_limit.get("resources", {}).get("core", {}).get("remaining", 5000)
            
            if remaining < 100:
                reset_time = rate_limit.get("resources", {}).get("core", {}).get("reset", 0)
                from datetime import datetime
                wait_seconds = reset_time - datetime.utcnow().timestamp() + 10
                if wait_seconds > 0:
                    self.log_event("WARN", f"Rate limit low ({remaining}), waiting {wait_seconds:.0f}s")
                    await asyncio.sleep(wait_seconds)
        except Exception as e:
            self.log_event("WARN", f"Could not check rate limit: {str(e)}")
    
    def _generate_apply_report(
        self, 
        plan: Dict[str, Any], 
        results: List[ActionResult]
    ) -> Dict[str, Any]:
        """Generate comprehensive apply report"""
        total_actions = len(results)
        successful = sum(1 for r in results if r.success)
        failed = total_actions - successful
        
        return {
            "version": "1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "plan_summary": plan.get("summary", {}),
            "execution_summary": {
                "total_actions": total_actions,
                "successful": successful,
                "failed": failed,
                "success_rate": f"{(successful/total_actions*100):.1f}%" if total_actions > 0 else "0%"
            },
            "actions": [r.to_dict() for r in results],
            "id_mappings": self.execution_context.get("id_mappings", {}),
            "errors": [r.to_dict() for r in results if not r.success]
        }
    
    def _generate_dry_run_report(
        self, 
        plan: Dict[str, Any], 
        results: List[ActionResult]
    ) -> Dict[str, Any]:
        """Generate comprehensive dry run report with predictions"""
        total_actions = len(results)
        successful = sum(1 for r in results if r.success)
        
        # Count outcomes
        outcome_counts = {
            "would_create": 0,
            "would_update": 0,
            "would_skip": 0,
            "would_fail": 0,
            "would_execute": 0
        }
        
        warnings = []
        
        for result in results:
            if result.simulated and result.simulation_outcome:
                outcome_counts[result.simulation_outcome] += 1
            
            # Check for actions requiring user input
            for action in plan.get("actions", []):
                if action.get("id") == result.action_id:
                    if action.get("requires_user_input"):
                        warnings.append(f"Action {result.action_id} requires manual configuration")
                    break
        
        # Add warnings for common issues
        if plan.get("user_inputs_required"):
            warnings.append(f"{len(plan['user_inputs_required'])} secrets/values need manual configuration")
        
        return {
            "version": "1.0",
            "mode": "dry_run",
            "timestamp": datetime.utcnow().isoformat(),
            "plan_summary": plan.get("summary", {}),
            "summary": {
                "total_actions": total_actions,
                "would_create": outcome_counts["would_create"],
                "would_update": outcome_counts["would_update"],
                "would_skip": outcome_counts["would_skip"],
                "would_fail": outcome_counts["would_fail"],
                "would_execute": outcome_counts["would_execute"],
                "simulation_success_rate": f"{(successful/total_actions*100):.1f}%" if total_actions > 0 else "0%"
            },
            "actions": [r.to_dict() for r in results],
            "warnings": warnings,
            "note": "This is a simulation. No actual changes were made to GitHub."
        }
    
    def _save_artifact(self, path: Path, data: Any):
        """Save artifact to file"""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            self.log_event("INFO", f"Saved artifact: {path}")
        except Exception as e:
            self.log_event("ERROR", f"Failed to save artifact {path}: {str(e)}")
    
    async def rollback_migration(self, executed_actions_path: str) -> Dict[str, Any]:
        """
        Rollback all executed actions from a failed migration.
        
        Args:
            executed_actions_path: Path to executed_actions.json file
            
        Returns:
            Dictionary with rollback results
        """
        self.log_event("INFO", "Starting rollback migration")
        
        try:
            # Load executed actions from file
            with open(executed_actions_path, 'r') as f:
                data = json.load(f)
                executed_actions = data.get("executed_actions", [])
            
            if not executed_actions:
                self.log_event("WARN", "No executed actions to rollback")
                return {
                    "status": "success",
                    "rolled_back": 0,
                    "skipped": 0,
                    "failed": 0,
                    "message": "No actions to rollback"
                }
            
            # Rollback in reverse order
            rollback_results = []
            rolled_back_count = 0
            skipped_count = 0
            failed_count = 0
            
            for action_data in reversed(executed_actions):
                action_id = action_data.get("action_id")
                action_type = action_data.get("action_type")
                reversible = action_data.get("reversible", True)
                rollback_data = action_data.get("rollback_data", {})
                
                if not reversible:
                    self.log_event("INFO", f"Skipping non-reversible action {action_id} ({action_type})")
                    skipped_count += 1
                    rollback_results.append({
                        "action_id": action_id,
                        "action_type": action_type,
                        "status": "skipped",
                        "reason": "non-reversible"
                    })
                    continue
                
                # Get action executor class
                action_class = ACTION_REGISTRY.get(action_type)
                if not action_class:
                    self.log_event("WARN", f"Unknown action type for rollback: {action_type}")
                    failed_count += 1
                    rollback_results.append({
                        "action_id": action_id,
                        "action_type": action_type,
                        "status": "failed",
                        "reason": f"unknown action type: {action_type}"
                    })
                    continue
                
                # Create action executor instance
                action_config = action_data.get("action_config", {})
                try:
                    action_executor = action_class(
                        action_config=action_config,
                        github_client=self.github_client,
                        context=self.execution_context
                    )
                    
                    # Attempt rollback
                    success = await action_executor.rollback(rollback_data)
                    
                    if success:
                        rolled_back_count += 1
                        self.log_event("INFO", f"Rolled back action {action_id} ({action_type})")
                        rollback_results.append({
                            "action_id": action_id,
                            "action_type": action_type,
                            "status": "success"
                        })
                    else:
                        failed_count += 1
                        self.log_event("ERROR", f"Failed to rollback action {action_id} ({action_type})")
                        rollback_results.append({
                            "action_id": action_id,
                            "action_type": action_type,
                            "status": "failed",
                            "reason": "rollback returned false"
                        })
                
                except Exception as e:
                    failed_count += 1
                    error_msg = f"Exception during rollback of action {action_id}: {str(e)}"
                    self.log_event("ERROR", error_msg)
                    rollback_results.append({
                        "action_id": action_id,
                        "action_type": action_type,
                        "status": "failed",
                        "reason": str(e)
                    })
            
            status = "success" if failed_count == 0 else "partial" if rolled_back_count > 0 else "failed"
            
            self.log_event("INFO", f"Rollback completed: {rolled_back_count} rolled back, {skipped_count} skipped, {failed_count} failed")
            
            return {
                "status": status,
                "rolled_back": rolled_back_count,
                "skipped": skipped_count,
                "failed": failed_count,
                "results": rollback_results
            }
            
        except FileNotFoundError:
            error_msg = f"Executed actions file not found: {executed_actions_path}"
            self.log_event("ERROR", error_msg)
            return {
                "status": "failed",
                "rolled_back": 0,
                "skipped": 0,
                "failed": 0,
                "error": error_msg
            }
        except Exception as e:
            error_msg = f"Rollback failed: {str(e)}"
            self.log_event("ERROR", error_msg)
            return {
                "status": "failed",
                "rolled_back": 0,
                "skipped": 0,
                "failed": 0,
                "error": error_msg
            }
    
    def generate_artifacts(self, data: Dict[str, Any]) -> Dict[str, str]:
        """Generate apply artifacts"""
        return {
            "apply_report": "apply/apply_report.json",
            "id_mappings": "apply/id_mappings.json",
            "errors": "apply/errors.json"
        }
