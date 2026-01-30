"""Base action executor for Apply Agent"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from datetime import datetime
from dataclasses import dataclass
import time
import asyncio
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ActionResult:
    """Result of an action execution"""
    success: bool
    action_id: str
    action_type: str
    outputs: Dict[str, Any]
    error: Optional[str] = None
    retry_count: int = 0
    duration_seconds: float = 0.0
    timestamp: Optional[datetime] = None
    simulated: bool = False
    simulation_outcome: Optional[str] = None  # "would_create", "would_update", "would_skip", "would_fail"
    simulation_message: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = {
            "success": self.success,
            "action_id": self.action_id,
            "action_type": self.action_type,
            "outputs": self.outputs,
            "error": self.error,
            "retry_count": self.retry_count,
            "duration_seconds": self.duration_seconds,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }
        if self.simulated:
            result["simulated"] = True
            result["simulation_outcome"] = self.simulation_outcome
            result["simulation_message"] = self.simulation_message
        return result


class BaseAction(ABC):
    """
    Base class for all action executors.
    
    Each action type implements this interface to execute
    a specific migration action on GitHub.
    """
    
    def __init__(self, action_config: Dict[str, Any], github_client: Any, context: Dict[str, Any]):
        """
        Initialize action executor.
        
        Args:
            action_config: Action configuration from plan
            github_client: GitHub API client (PyGithub)
            context: Execution context (shared state, mappings, etc.)
        """
        self.action_id = action_config.get("id")
        self.action_type = action_config.get("type")
        self.parameters = action_config.get("parameters", {})
        self.idempotency_key = action_config.get("idempotency_key")
        self.github_client = github_client
        self.context = context
        self.logger = get_logger(f"{__name__}.{self.action_type}")
    
    @abstractmethod
    async def execute(self) -> ActionResult:
        """
        Execute the action.
        
        Returns:
            ActionResult with success status and outputs
        """
        pass
    
    async def simulate(self) -> ActionResult:
        """
        Simulate the action without executing it.
        Predicts the outcome of executing the action.
        
        Returns:
            ActionResult with simulated=True and predicted outcome
        """
        # Default implementation - subclasses can override for specific behavior
        return ActionResult(
            success=True,
            action_id=self.action_id,
            action_type=self.action_type,
            outputs={},
            simulated=True,
            simulation_outcome="would_execute",
            simulation_message=f"Would execute action: {self.action_type}"
        )
    
    def check_idempotency(self) -> Optional[ActionResult]:
        """
        Check if action has already been executed.
        
        Returns:
            Previous action result if found, None otherwise
        """
        if not self.idempotency_key:
            return None
        
        executed_actions = self.context.get("executed_actions", {})
        return executed_actions.get(self.idempotency_key)
    
    def mark_executed(self, result: ActionResult):
        """Mark action as executed in context"""
        if self.idempotency_key:
            if "executed_actions" not in self.context:
                self.context["executed_actions"] = {}
            self.context["executed_actions"][self.idempotency_key] = result
    
    def get_id_mapping(self, gitlab_type: str, gitlab_id: Any) -> Optional[Any]:
        """Get mapped GitHub ID for a GitLab ID"""
        mappings = self.context.get("id_mappings", {})
        type_mappings = mappings.get(gitlab_type, {})
        return type_mappings.get(str(gitlab_id))
    
    def set_id_mapping(self, gitlab_type: str, gitlab_id: Any, github_id: Any):
        """Store ID mapping from GitLab to GitHub"""
        if "id_mappings" not in self.context:
            self.context["id_mappings"] = {}
        if gitlab_type not in self.context["id_mappings"]:
            self.context["id_mappings"][gitlab_type] = {}
        self.context["id_mappings"][gitlab_type][str(gitlab_id)] = github_id
    
    async def execute_with_retry(self, max_retries: int = 3, base_delay: float = 1.0, dry_run: bool = False) -> ActionResult:
        """
        Execute action with retry logic and exponential backoff.
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds for exponential backoff
            dry_run: If True, simulate instead of executing
            
        Returns:
            ActionResult
        """
        # In dry-run mode, call simulate() instead of execute()
        if dry_run:
            self.logger.info(f"Simulating action {self.action_id}")
            start_time = time.time()
            result = await self.simulate()
            result.duration_seconds = time.time() - start_time
            return result
        
        # Check idempotency first
        previous_result = self.check_idempotency()
        if previous_result:
            self.logger.info(f"Action {self.action_id} already executed (idempotency)")
            return previous_result
        
        attempt = 0
        last_error = None
        start_time = time.time()
        
        while attempt < max_retries:
            try:
                self.logger.info(f"Executing action {self.action_id} (attempt {attempt + 1}/{max_retries})")
                
                result = await self.execute()
                result.retry_count = attempt
                result.duration_seconds = time.time() - start_time
                
                if result.success:
                    self.mark_executed(result)
                    self.logger.info(f"Action {self.action_id} completed successfully")
                    return result
                else:
                    last_error = result.error
                    
            except Exception as e:
                last_error = str(e)
                self.logger.error(f"Action {self.action_id} failed (attempt {attempt + 1}): {last_error}")
            
            attempt += 1
            if attempt < max_retries:
                # Exponential backoff
                delay = base_delay * (2 ** attempt)
                self.logger.info(f"Retrying in {delay:.1f} seconds...")
                await asyncio.sleep(delay)  # Use async sleep to not block event loop
        
        # All retries exhausted
        duration = time.time() - start_time
        result = ActionResult(
            success=False,
            action_id=self.action_id,
            action_type=self.action_type,
            outputs={},
            error=f"Failed after {max_retries} attempts: {last_error}",
            retry_count=attempt,
            duration_seconds=duration
        )
        return result
