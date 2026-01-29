"""Base transformer class for GitLab to GitHub transformations"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TransformationResult:
    """Result of a transformation operation"""
    
    success: bool
    data: Optional[Dict[str, Any]] = None
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def add_error(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Add an error to the result"""
        self.errors.append({
            "message": message,
            "context": context or {},
            "timestamp": datetime.utcnow().isoformat()
        })
        self.success = False
    
    def add_warning(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Add a warning to the result"""
        self.warnings.append({
            "message": message,
            "context": context or {},
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return {
            "success": self.success,
            "data": self.data,
            "errors": self.errors,
            "warnings": self.warnings,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }


class BaseTransformer(ABC):
    """
    Base class for all GitLab to GitHub transformers.
    
    Provides common functionality:
    - Error handling and logging
    - Result tracking
    - Context management
    - Validation
    """
    
    def __init__(self, name: str):
        """
        Initialize the transformer.
        
        Args:
            name: Name of the transformer
        """
        self.name = name
        self.logger = get_logger(f"{__name__}.{name}")
        self.context: Dict[str, Any] = {}
    
    @abstractmethod
    def transform(self, input_data: Dict[str, Any]) -> TransformationResult:
        """
        Transform GitLab data to GitHub format.
        
        Args:
            input_data: GitLab data to transform
            
        Returns:
            TransformationResult with transformed data
        """
        pass
    
    def validate_input(self, input_data: Dict[str, Any], required_fields: List[str]) -> TransformationResult:
        """
        Validate input data has required fields.
        
        Args:
            input_data: Input data to validate
            required_fields: List of required field names
            
        Returns:
            TransformationResult indicating validation success/failure
        """
        result = TransformationResult(success=True)
        
        for field in required_fields:
            if field not in input_data:
                result.add_error(
                    f"Missing required field: {field}",
                    {"transformer": self.name, "field": field}
                )
        
        return result
    
    def set_context(self, key: str, value: Any):
        """Set a context value"""
        self.context[key] = value
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """Get a context value"""
        return self.context.get(key, default)
    
    def log_transform_start(self, input_type: str):
        """Log the start of a transformation"""
        self.logger.info(f"Starting {self.name} transformation for {input_type}")
    
    def log_transform_complete(self, success: bool, details: Optional[str] = None):
        """Log the completion of a transformation"""
        status = "successfully" if success else "with errors"
        message = f"{self.name} transformation completed {status}"
        if details:
            message += f": {details}"
        
        if success:
            self.logger.info(message)
        else:
            self.logger.error(message)
