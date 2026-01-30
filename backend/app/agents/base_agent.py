"""Base agent class using Microsoft Agent Framework"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from datetime import datetime
import asyncio
import httpx
from app.utils.logging import get_logger
from app.agents.azure_ai_client import create_agent_with_instructions
from app.utils.errors import create_gitlab_error, create_github_error, MigrationError

logger = get_logger(__name__)


class BaseAgent(ABC):
    """
    Base class for all migration agents using Microsoft Agent Framework.
    
    Uses the actual MAF library when Azure AI is configured, otherwise falls
    back to deterministic implementations for offline/local usage.
    
    Each agent is a specialized entity with:
    - Clear input/output contracts
    - Deterministic behavior
    - Error handling with retries
    - Progress tracking via events
    - Context awareness
    - Tool integration capabilities (when using MAF)
    """
    
    def __init__(self, agent_name: str, instructions: str):
        """
        Initialize the base agent.
        
        Args:
            agent_name: Name of the agent (e.g., "DiscoveryAgent")
            instructions: Natural language instructions for the agent's role
        """
        self.agent_name = agent_name
        self.instructions = instructions
        self.context = {}
        self.logger = get_logger(f"{__name__}.{agent_name}")
        self.maf_agent = None  # Will be initialized async
        self._maf_initialized = False
    
    async def initialize_maf_agent(self):
        """
        Initialize Microsoft Agent Framework agent (async).
        
        Call this before using the agent if you want MAF support.
        Falls back gracefully to local implementation if MAF not available.
        """
        if not self._maf_initialized:
            self.maf_agent = await create_agent_with_instructions(
                instructions=self.instructions,
                name=self.agent_name
            )
            self._maf_initialized = True
            
            if self.maf_agent:
                self.log_event("INFO", "MAF agent initialized successfully")
            else:
                self.log_event("INFO", "Using local implementation (MAF not available)")
    
    @abstractmethod
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the agent's main task.
        
        Args:
            inputs: Input configuration and parameters
            
        Returns:
            Dict containing:
                - status: "success" | "failed" | "partial"
                - outputs: Agent-specific output data
                - artifacts: List of generated artifacts
                - errors: List of errors encountered
        """
        pass
    
    @abstractmethod
    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        """
        Validate input parameters before execution.
        
        Args:
            inputs: Input parameters to validate
            
        Returns:
            True if inputs are valid, False otherwise
        """
        pass
    
    @abstractmethod
    def generate_artifacts(self, data: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate output artifacts from execution data.
        
        Args:
            data: Execution result data
            
        Returns:
            Dict mapping artifact names to file paths
        """
        pass
    
    def handle_error(self, exception: Exception, context: Optional[str] = None) -> MigrationError:
        """
        Handle an exception and convert it to a user-friendly MigrationError.
        
        Args:
            exception: The exception to handle
            context: Optional context (e.g., project path, resource name)
            
        Returns:
            MigrationError with user-friendly messaging
        """
        # Determine error type and create appropriate error
        if isinstance(exception, httpx.HTTPError):
            # Try to determine if it's GitLab or GitHub based on context
            if context and 'github' in context.lower():
                migration_error = create_github_error(exception, context)
            else:
                migration_error = create_gitlab_error(exception, context)
        else:
            # Generic error - create a simple MigrationError
            migration_error = MigrationError(
                category="unknown",
                code="AGENT_ERROR_001",
                message=f"An error occurred in {self.agent_name}",
                technical=f"{type(exception).__name__}: {str(exception)}",
                suggestion="Check the technical details for more information. If the problem persists, contact support.",
                raw_error=exception
            )
        
        # Log the error with full context
        self.log_event(
            "ERROR",
            migration_error.message,
            {
                "error_code": migration_error.code,
                "category": migration_error.category,
                "technical": migration_error.technical,
                "suggestion": migration_error.suggestion,
                "context": context
            }
        )
        
        return migration_error
    
    def log_event(self, level: str, message: str, payload: Optional[Dict] = None):
        """
        Log an event for tracking and debugging.
        
        Args:
            level: Log level (INFO, WARN, ERROR, DEBUG)
            message: Log message
            payload: Additional structured data
        """
        log_data = {
            "agent": self.agent_name,
            "timestamp": datetime.utcnow().isoformat(),
            "event_payload": payload or {}  # Renamed to avoid conflict with 'message'
        }
        
        if level == "ERROR":
            self.logger.error(message, extra=log_data)
        elif level == "WARN":
            self.logger.warning(message, extra=log_data)
        elif level == "DEBUG":
            self.logger.debug(message, extra=log_data)
        else:
            self.logger.info(message, extra=log_data)
    
    async def run_with_retry(
        self, 
        inputs: Dict[str, Any], 
        max_retries: int = 3,
        retry_delay: int = 5
    ) -> Dict[str, Any]:
        """
        Execute the agent with automatic retry on failure.
        
        Args:
            inputs: Input parameters
            max_retries: Maximum number of retry attempts
            retry_delay: Delay in seconds between retries
            
        Returns:
            Execution result
        """
        attempt = 0
        last_error = None
        
        while attempt < max_retries:
            try:
                self.log_event("INFO", f"Starting execution (attempt {attempt + 1}/{max_retries})")
                
                # Validate inputs
                if not self.validate_inputs(inputs):
                    raise ValueError("Input validation failed")
                
                # Execute main task
                result = await self.execute(inputs)
                
                if result.get("status") == "success":
                    self.log_event("INFO", "Execution completed successfully")
                    return result
                elif result.get("status") == "partial":
                    self.log_event("WARN", "Execution completed with partial success", 
                                 {"errors": result.get("errors", [])})
                    return result
                else:
                    raise Exception(f"Execution failed: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                # Handle the error and create user-friendly message
                migration_error = self.handle_error(e, inputs.get("project_path") or inputs.get("context"))
                last_error = migration_error
                attempt += 1
                
                if attempt < max_retries:
                    self.log_event("INFO", f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
        
        # All retries exhausted - format error for return
        error_dict = last_error.to_dict() if isinstance(last_error, MigrationError) else {
            "category": "unknown",
            "code": "UNKNOWN",
            "message": str(last_error),
            "technical": str(last_error),
            "suggestion": "Review the error details and try again"
        }
        
        return {
            "status": "failed",
            "error": error_dict.get("message", str(last_error)),
            "error_details": error_dict,
            "outputs": {},
            "artifacts": [],
            "errors": [error_dict]
        }
    
    def update_context(self, key: str, value: Any):
        """
        Update agent context for maintaining state across operations.
        
        Args:
            key: Context key
            value: Context value
        """
        self.context[key] = value
        self.log_event("DEBUG", f"Context updated: {key}")
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """
        Get value from agent context.
        
        Args:
            key: Context key
            default: Default value if key not found
            
        Returns:
            Context value or default
        """
        return self.context.get(key, default)
    
    def clear_context(self):
        """Clear agent context."""
        self.context = {}
        self.log_event("DEBUG", "Context cleared")


class AgentResult:
    """Standard result format for agent execution"""
    
    def __init__(
        self,
        status: str,
        outputs: Dict[str, Any],
        artifacts: list[str],
        errors: list[Dict[str, Any]] = None
    ):
        self.status = status
        self.outputs = outputs
        self.artifacts = artifacts
        self.errors = errors or []
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return {
            "status": self.status,
            "outputs": self.outputs,
            "artifacts": self.artifacts,
            "errors": self.errors,
            "timestamp": self.timestamp.isoformat()
        }
    
    def is_success(self) -> bool:
        """Check if execution was successful"""
        return self.status == "success"
    
    def is_partial_success(self) -> bool:
        """Check if execution had partial success"""
        return self.status == "partial"
    
    def has_errors(self) -> bool:
        """Check if execution had errors"""
        return len(self.errors) > 0
