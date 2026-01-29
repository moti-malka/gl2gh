"""
Health check endpoints for monitoring and orchestration.

Provides endpoints for liveness and readiness checks that can be used by
Kubernetes, Docker, load balancers, and monitoring systems.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class HealthStatus:
    """Health status information."""
    
    def __init__(self):
        self.start_time = time.time()
        self.last_successful_operation = time.time()
        self.total_operations = 0
        self.failed_operations = 0
        self.dependencies: dict[str, dict[str, Any]] = {}
    
    def record_operation(self, success: bool) -> None:
        """Record an operation outcome."""
        self.total_operations += 1
        if success:
            self.last_successful_operation = time.time()
        else:
            self.failed_operations += 1
    
    def add_dependency(self, name: str, status: str, details: dict[str, Any] | None = None) -> None:
        """Add or update a dependency status."""
        self.dependencies[name] = {
            "status": status,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
        }
    
    def get_uptime_seconds(self) -> float:
        """Get uptime in seconds."""
        return time.time() - self.start_time
    
    def get_error_rate(self) -> float:
        """Get error rate (0.0 to 1.0)."""
        if self.total_operations == 0:
            return 0.0
        return self.failed_operations / self.total_operations
    
    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        # Check if we've had recent successful operations
        time_since_success = time.time() - self.last_successful_operation
        if time_since_success > 300:  # 5 minutes
            logger.warning(f"No successful operations in {time_since_success:.0f} seconds")
            return False
        
        # Check error rate
        if self.get_error_rate() > 0.5:  # More than 50% errors
            logger.warning(f"High error rate: {self.get_error_rate():.2%}")
            return False
        
        # Check dependencies
        for name, dep in self.dependencies.items():
            if dep["status"] == "unhealthy":
                logger.warning(f"Dependency unhealthy: {name}")
                return False
        
        return True
    
    def is_ready(self) -> bool:
        """Check if service is ready to accept requests."""
        # Service is ready if all critical dependencies are healthy
        critical_deps = ["gitlab_api"]
        for dep in critical_deps:
            if dep in self.dependencies:
                if self.dependencies[dep]["status"] != "healthy":
                    logger.warning(f"Critical dependency not ready: {dep}")
                    return False
        
        return True


# Global health status instance
_health_status = HealthStatus()


def get_health_status() -> HealthStatus:
    """Get global health status instance."""
    return _health_status


def liveness_check() -> dict[str, Any]:
    """
    Liveness probe endpoint.
    
    Returns basic information about whether the service is running.
    This should always return success unless the process is dead.
    
    Returns:
        Dict with liveness status and basic info
    """
    status = get_health_status()
    
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": status.get_uptime_seconds(),
        "service": "discovery-agent",
        "version": "0.1.0",
    }


def readiness_check() -> dict[str, Any]:
    """
    Readiness probe endpoint.
    
    Returns information about whether the service is ready to handle requests.
    This checks dependencies and recent operation success.
    
    Returns:
        Dict with readiness status and detailed checks
    """
    status = get_health_status()
    is_ready = status.is_ready()
    
    return {
        "status": "ready" if is_ready else "not_ready",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "dependencies": status.dependencies,
            "total_operations": status.total_operations,
            "failed_operations": status.failed_operations,
            "error_rate": status.get_error_rate(),
        },
    }


def health_check() -> dict[str, Any]:
    """
    Full health check endpoint.
    
    Returns comprehensive health information including dependencies,
    metrics, and detailed status.
    
    Returns:
        Dict with full health status
    """
    status = get_health_status()
    is_healthy = status.is_healthy()
    
    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": status.get_uptime_seconds(),
        "service": "discovery-agent",
        "version": "0.1.0",
        "metrics": {
            "total_operations": status.total_operations,
            "failed_operations": status.failed_operations,
            "error_rate": status.get_error_rate(),
            "last_successful_operation": datetime.fromtimestamp(
                status.last_successful_operation, tz=timezone.utc
            ).isoformat(),
        },
        "dependencies": status.dependencies,
    }


def check_gitlab_api(base_url: str, timeout: int = 5) -> bool:
    """
    Check GitLab API availability.
    
    Args:
        base_url: GitLab instance URL
        timeout: Request timeout in seconds
        
    Returns:
        True if API is reachable
    """
    try:
        import requests
        
        # Try to reach the version endpoint (doesn't require auth)
        response = requests.get(
            f"{base_url}/api/v4/version",
            timeout=timeout,
            allow_redirects=True,
        )
        
        is_healthy = response.status_code == 200 or response.status_code == 401
        
        get_health_status().add_dependency(
            "gitlab_api",
            "healthy" if is_healthy else "unhealthy",
            {
                "base_url": base_url,
                "status_code": response.status_code,
                "response_time_ms": response.elapsed.total_seconds() * 1000,
            },
        )
        
        return is_healthy
        
    except Exception as e:
        logger.error(f"GitLab API health check failed: {e}")
        get_health_status().add_dependency(
            "gitlab_api",
            "unhealthy",
            {
                "base_url": base_url,
                "error": str(e),
            },
        )
        return False
