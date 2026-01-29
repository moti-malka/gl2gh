"""
Structured logging configuration for production readiness.

Provides JSON-formatted logging with proper log levels, correlation IDs,
and integration with monitoring systems.
"""

from __future__ import annotations

import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from typing import Any


class StructuredFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    
    Produces logs in JSON format suitable for log aggregation systems like
    ELK, Splunk, or CloudWatch.
    """
    
    def __init__(
        self,
        include_exc_info: bool = True,
        extra_fields: dict[str, Any] | None = None,
    ):
        super().__init__()
        self.include_exc_info = include_exc_info
        self.extra_fields = extra_fields or {}
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add process/thread info
        log_data["process"] = {
            "id": record.process,
            "name": record.processName,
        }
        log_data["thread"] = {
            "id": record.thread,
            "name": record.threadName,
        }
        
        # Add any extra fields from the formatter config
        log_data.update(self.extra_fields)
        
        # Add extra fields from the log record
        if hasattr(record, "correlation_id"):
            log_data["correlation_id"] = record.correlation_id
        
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        
        if hasattr(record, "api_endpoint"):
            log_data["api_endpoint"] = record.api_endpoint
        
        if hasattr(record, "status_code"):
            log_data["status_code"] = record.status_code
        
        # Add exception info if present
        if self.include_exc_info and record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }
        
        return json.dumps(log_data, ensure_ascii=False)


class HumanReadableFormatter(logging.Formatter):
    """
    Human-readable formatter for console output.
    
    Provides colored output and structured information in a readable format.
    """
    
    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[32m",       # Green
        "WARNING": "\033[33m",    # Yellow
        "ERROR": "\033[31m",      # Red
        "CRITICAL": "\033[35m",   # Magenta
        "RESET": "\033[0m",       # Reset
    }
    
    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors and sys.stdout.isatty()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record for human reading."""
        # Color the level name
        levelname = record.levelname
        if self.use_colors:
            color = self.COLORS.get(levelname, self.COLORS["RESET"])
            levelname = f"{color}{levelname:8}{self.COLORS['RESET']}"
        else:
            levelname = f"{levelname:8}"
        
        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%H:%M:%S")
        
        # Base message
        message = record.getMessage()
        
        # Add extra context if available
        extra_info = []
        if hasattr(record, "duration_ms"):
            extra_info.append(f"duration={record.duration_ms}ms")
        if hasattr(record, "status_code"):
            extra_info.append(f"status={record.status_code}")
        if hasattr(record, "correlation_id"):
            extra_info.append(f"correlation_id={record.correlation_id}")
        
        if extra_info:
            message = f"{message} [{', '.join(extra_info)}]"
        
        # Format exception if present
        exc_text = ""
        if record.exc_info:
            exc_text = "\n" + "".join(traceback.format_exception(*record.exc_info))
        
        return f"{timestamp} {levelname} {record.name}: {message}{exc_text}"


def setup_structured_logging(
    level: int = logging.INFO,
    json_format: bool = False,
    log_file: str | None = None,
    service_name: str = "discovery-agent",
    environment: str = "development",
) -> logging.Logger:
    """
    Setup structured logging for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: If True, use JSON formatter; otherwise human-readable
        log_file: Optional file path for log output
        service_name: Name of the service for log context
        environment: Environment name (development, staging, production)
        
    Returns:
        Configured logger for the discovery_agent package
    """
    # Remove existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Choose formatter
    if json_format:
        formatter = StructuredFormatter(
            extra_fields={
                "service": service_name,
                "environment": environment,
            }
        )
    else:
        formatter = HumanReadableFormatter(use_colors=True)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    
    # Configure root logger
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        root_logger.addHandler(file_handler)
    
    # Get package logger
    logger = logging.getLogger("discovery_agent")
    logger.setLevel(level)
    
    logger.info(
        "Logging configured",
        extra={
            "json_format": json_format,
            "log_file": log_file,
            "environment": environment,
        },
    )
    
    return logger


class LogContext:
    """
    Context manager for adding structured context to logs.
    
    Example:
        with LogContext(correlation_id="abc-123", user_id="user@example.com"):
            logger.info("Processing request")
    """
    
    def __init__(self, **kwargs):
        self.context = kwargs
        self.old_factory = None
    
    def __enter__(self):
        """Add context to log records."""
        self.old_factory = logging.getLogRecordFactory()
        
        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            for key, value in self.context.items():
                setattr(record, key, value)
            return record
        
        logging.setLogRecordFactory(record_factory)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore original log record factory."""
        if self.old_factory:
            logging.setLogRecordFactory(self.old_factory)


def log_api_call(
    logger: logging.Logger,
    method: str,
    url: str,
    status_code: int,
    duration_ms: float,
    correlation_id: str | None = None,
) -> None:
    """
    Log an API call with structured information.
    
    Args:
        logger: Logger instance
        method: HTTP method (GET, POST, etc.)
        url: API endpoint URL
        status_code: HTTP status code
        duration_ms: Request duration in milliseconds
        correlation_id: Optional correlation ID for tracking
    """
    extra = {
        "api_endpoint": url,
        "status_code": status_code,
        "duration_ms": duration_ms,
        "http_method": method,
    }
    
    if correlation_id:
        extra["correlation_id"] = correlation_id
    
    level = logging.INFO
    if status_code >= 500:
        level = logging.ERROR
    elif status_code >= 400:
        level = logging.WARNING
    
    logger.log(
        level,
        f"{method} {url} -> {status_code} ({duration_ms:.0f}ms)",
        extra=extra,
    )
