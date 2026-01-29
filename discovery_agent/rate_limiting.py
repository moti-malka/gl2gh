"""
Enhanced rate limiting for GitLab and GitHub APIs.

Provides intelligent rate limit handling with backoff strategies,
rate limit monitoring, and predictive throttling.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Callable, Any

logger = logging.getLogger(__name__)


@dataclass
class RateLimitInfo:
    """Rate limit information for an API."""
    limit: int | None = None
    remaining: int | None = None
    reset_at: datetime | None = None
    retry_after: int | None = None
    
    @property
    def is_exhausted(self) -> bool:
        """Check if rate limit is exhausted."""
        if self.remaining is not None:
            return self.remaining <= 0
        return False
    
    @property
    def seconds_until_reset(self) -> float | None:
        """Get seconds until rate limit resets."""
        if self.reset_at:
            delta = self.reset_at - datetime.now(timezone.utc)
            return max(0, delta.total_seconds())
        return None
    
    @property
    def usage_percent(self) -> float:
        """Get rate limit usage as percentage (0.0 to 1.0)."""
        if self.limit and self.remaining is not None:
            used = self.limit - self.remaining
            return used / self.limit
        return 0.0


class RateLimiter:
    """
    Adaptive rate limiter with exponential backoff.
    
    Features:
    - Tracks rate limit state
    - Automatic backoff when limits are approached
    - Respects Retry-After headers
    - Predictive throttling to avoid hitting limits
    """
    
    def __init__(
        self,
        name: str,
        default_limit: int = 1000,
        window_seconds: int = 3600,
        throttle_threshold: float = 0.8,
    ):
        """
        Initialize rate limiter.
        
        Args:
            name: Name of this rate limiter (for logging)
            default_limit: Default rate limit per window
            window_seconds: Time window in seconds
            throttle_threshold: Start throttling at this usage percentage (0.0-1.0)
        """
        self.name = name
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self.throttle_threshold = throttle_threshold
        
        self.lock = Lock()
        self.info = RateLimitInfo(limit=default_limit, remaining=default_limit)
        self.last_request_time = 0.0
        self.request_count = 0
        self.throttle_delay = 0.0
    
    def update_from_headers(self, headers: dict[str, str]) -> None:
        """
        Update rate limit info from API response headers.
        
        Supports both GitLab and GitHub header formats.
        
        Args:
            headers: HTTP response headers
        """
        with self.lock:
            # GitLab headers
            if "RateLimit-Limit" in headers:
                self.info.limit = int(headers["RateLimit-Limit"])
            if "RateLimit-Remaining" in headers:
                self.info.remaining = int(headers["RateLimit-Remaining"])
            if "RateLimit-Reset" in headers:
                reset_timestamp = int(headers["RateLimit-Reset"])
                self.info.reset_at = datetime.fromtimestamp(reset_timestamp, tz=timezone.utc)
            
            # GitHub headers
            if "X-RateLimit-Limit" in headers:
                self.info.limit = int(headers["X-RateLimit-Limit"])
            if "X-RateLimit-Remaining" in headers:
                self.info.remaining = int(headers["X-RateLimit-Remaining"])
            if "X-RateLimit-Reset" in headers:
                reset_timestamp = int(headers["X-RateLimit-Reset"])
                self.info.reset_at = datetime.fromtimestamp(reset_timestamp, tz=timezone.utc)
            
            # Retry-After header (429 responses)
            if "Retry-After" in headers:
                self.info.retry_after = int(headers["Retry-After"])
            
            # Update throttle delay based on usage
            self._update_throttle_delay()
    
    def _update_throttle_delay(self) -> None:
        """Calculate adaptive throttle delay based on rate limit usage."""
        usage = self.info.usage_percent
        
        if usage >= self.throttle_threshold:
            # Exponentially increase delay as we approach the limit
            excess = (usage - self.throttle_threshold) / (1.0 - self.throttle_threshold)
            self.throttle_delay = excess * 2.0  # Up to 2 seconds delay
            
            logger.warning(
                f"{self.name}: Rate limit at {usage:.1%}, throttling with {self.throttle_delay:.2f}s delay"
            )
        else:
            self.throttle_delay = 0.0
    
    def wait_if_needed(self) -> None:
        """
        Wait if rate limit requires throttling.
        
        This method blocks if:
        - Rate limit is exhausted (waits until reset)
        - Usage is high (applies adaptive throttle delay)
        - Retry-After header was received
        """
        with self.lock:
            now = time.time()
            
            # Check if we need to wait for rate limit reset
            if self.info.is_exhausted:
                wait_time = self.info.seconds_until_reset
                if wait_time and wait_time > 0:
                    logger.warning(
                        f"{self.name}: Rate limit exhausted, waiting {wait_time:.0f}s until reset"
                    )
                    time.sleep(wait_time + 1)  # Add 1s buffer
                    # Reset rate limit info after waiting
                    self.info.remaining = self.info.limit
                    return
            
            # Check for explicit retry-after
            if self.info.retry_after:
                logger.warning(f"{self.name}: Retry-After received, waiting {self.info.retry_after}s")
                time.sleep(self.info.retry_after)
                self.info.retry_after = None
                return
            
            # Apply adaptive throttle delay
            if self.throttle_delay > 0:
                time.sleep(self.throttle_delay)
            
            # Ensure minimum time between requests (100ms)
            min_interval = 0.1
            time_since_last = now - self.last_request_time
            if time_since_last < min_interval:
                time.sleep(min_interval - time_since_last)
            
            self.last_request_time = time.time()
            self.request_count += 1
    
    def get_status(self) -> dict[str, Any]:
        """Get current rate limit status."""
        with self.lock:
            return {
                "name": self.name,
                "limit": self.info.limit,
                "remaining": self.info.remaining,
                "usage_percent": self.info.usage_percent,
                "reset_at": self.info.reset_at.isoformat() if self.info.reset_at else None,
                "seconds_until_reset": self.info.seconds_until_reset,
                "throttle_delay": self.throttle_delay,
                "request_count": self.request_count,
            }


class RateLimiterRegistry:
    """Registry for managing multiple rate limiters."""
    
    def __init__(self):
        self.limiters: dict[str, RateLimiter] = {}
        self.lock = Lock()
    
    def get_or_create(
        self,
        name: str,
        default_limit: int = 1000,
        window_seconds: int = 3600,
        throttle_threshold: float = 0.8,
    ) -> RateLimiter:
        """Get existing rate limiter or create a new one."""
        with self.lock:
            if name not in self.limiters:
                self.limiters[name] = RateLimiter(
                    name=name,
                    default_limit=default_limit,
                    window_seconds=window_seconds,
                    throttle_threshold=throttle_threshold,
                )
            return self.limiters[name]
    
    def get_all_status(self) -> dict[str, Any]:
        """Get status of all rate limiters."""
        with self.lock:
            return {
                name: limiter.get_status()
                for name, limiter in self.limiters.items()
            }


# Global registry
_registry = RateLimiterRegistry()


def get_rate_limiter(
    name: str,
    default_limit: int = 1000,
    window_seconds: int = 3600,
    throttle_threshold: float = 0.8,
) -> RateLimiter:
    """
    Get or create a rate limiter.
    
    Args:
        name: Name of the rate limiter
        default_limit: Default rate limit per window
        window_seconds: Time window in seconds
        throttle_threshold: Start throttling at this usage percentage
        
    Returns:
        Rate limiter instance
    """
    return _registry.get_or_create(name, default_limit, window_seconds, throttle_threshold)


def get_all_rate_limiter_status() -> dict[str, Any]:
    """Get status of all rate limiters."""
    return _registry.get_all_status()


# Pre-configured rate limiters for common APIs
gitlab_rate_limiter = get_rate_limiter(
    "gitlab",
    default_limit=2000,  # GitLab default for authenticated users
    window_seconds=60,
    throttle_threshold=0.8,
)

github_rate_limiter = get_rate_limiter(
    "github",
    default_limit=5000,  # GitHub default for authenticated users
    window_seconds=3600,
    throttle_threshold=0.8,
)


def rate_limited(limiter: RateLimiter) -> Callable:
    """
    Decorator for rate-limited functions.
    
    Example:
        @rate_limited(gitlab_rate_limiter)
        def fetch_projects():
            # This will be rate limited
            pass
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            limiter.wait_if_needed()
            return func(*args, **kwargs)
        return wrapper
    return decorator
