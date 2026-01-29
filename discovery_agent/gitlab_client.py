"""
GitLab REST API Client with pagination and backoff support.

Supports both GitLab SaaS and self-managed instances.
Only performs GET requests (read-only, safe operations).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Generator, Iterator
from urllib.parse import urlencode, urljoin

import requests
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)


@dataclass
class APICallStats:
    """Track API call statistics."""
    total_calls: int = 0
    successful_calls: int = 0
    retried_calls: int = 0
    failed_calls: int = 0


@dataclass
class GitLabResponse:
    """Wrapper for GitLab API responses."""
    status_code: int
    data: Any
    headers: dict[str, str]
    
    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300
    
    @property
    def next_page(self) -> str | None:
        """Get next page number from GitLab pagination headers."""
        return self.headers.get("X-Next-Page") or self.headers.get("x-next-page")
    
    @property
    def total_pages(self) -> int | None:
        """Get total pages from GitLab pagination headers."""
        val = self.headers.get("X-Total-Pages") or self.headers.get("x-total-pages")
        return int(val) if val else None
    
    @property
    def total_items(self) -> int | None:
        """Get total items from GitLab pagination headers."""
        val = self.headers.get("X-Total") or self.headers.get("x-total")
        return int(val) if val else None


class GitLabClientError(Exception):
    """Base exception for GitLab client errors."""
    def __init__(self, message: str, status_code: int | None = None, response: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class RateLimitError(GitLabClientError):
    """Raised when rate limit is exceeded."""
    def __init__(self, retry_after: int | None = None):
        super().__init__(f"Rate limit exceeded. Retry after: {retry_after}s")
        self.retry_after = retry_after


class GitLabClient:
    """
    GitLab REST API client with pagination and exponential backoff.
    
    Features:
    - Automatic pagination via X-Next-Page headers
    - Exponential backoff for rate limits (429) and server errors (5xx)
    - Respects Retry-After header
    - Read-only operations only (GET requests)
    - API call tracking/statistics
    
    Usage:
        client = GitLabClient("https://gitlab.com", "your-token")
        status, data, headers = client.get("/api/v4/projects")
        for item in client.paginate("/api/v4/groups/123/projects"):
            print(item)
    """
    
    DEFAULT_TIMEOUT = 30
    DEFAULT_PER_PAGE = 100
    MAX_RETRIES = 5
    BASE_BACKOFF_SECONDS = 1.0
    MAX_BACKOFF_SECONDS = 60.0
    
    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        verify_ssl: bool = True,
    ):
        """
        Initialize GitLab client.
        
        Args:
            base_url: GitLab instance URL (e.g., "https://gitlab.com")
            token: Personal Access Token for authentication
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
            verify_ssl: Whether to verify SSL certificates
        """
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.max_retries = max_retries
        self.verify_ssl = verify_ssl
        self.stats = APICallStats()
        
        # Create session for connection pooling
        self._session = requests.Session()
        self._session.headers.update({
            "PRIVATE-TOKEN": token,
            "Accept": "application/json",
            "User-Agent": "GitLab-Discovery-Agent/0.1.0",
        })
        self._session.verify = verify_ssl
    
    def _build_url(self, path: str) -> str:
        """Build full URL from path."""
        if path.startswith("http://") or path.startswith("https://"):
            return path
        # Ensure path starts with /
        if not path.startswith("/"):
            path = "/" + path
        return urljoin(self.base_url, path)
    
    def _calculate_backoff(self, attempt: int, retry_after: int | None = None) -> float:
        """Calculate backoff time with exponential increase."""
        if retry_after is not None:
            return min(float(retry_after), self.MAX_BACKOFF_SECONDS)
        # Exponential backoff: 1, 2, 4, 8, 16, ...
        backoff = self.BASE_BACKOFF_SECONDS * (2 ** attempt)
        return min(backoff, self.MAX_BACKOFF_SECONDS)
    
    def _should_retry(self, status_code: int) -> bool:
        """Determine if request should be retried based on status code."""
        # Retry on rate limit (429) or server errors (5xx)
        return status_code == 429 or (500 <= status_code < 600)
    
    def _get_retry_after(self, headers: dict[str, str]) -> int | None:
        """Extract Retry-After header value."""
        retry_after = headers.get("Retry-After") or headers.get("retry-after")
        if retry_after:
            try:
                return int(retry_after)
            except ValueError:
                pass
        return None
    
    def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> tuple[int, Any, dict[str, str]]:
        """
        Perform GET request with automatic retry and backoff.
        
        Args:
            path: API endpoint path (e.g., "/api/v4/projects")
            params: Query parameters
            
        Returns:
            Tuple of (status_code, json_or_text, headers)
            
        Raises:
            GitLabClientError: On unrecoverable errors after retries
        """
        url = self._build_url(path)
        params = params or {}
        
        last_error: Exception | None = None
        last_status: int | None = None
        last_response: Any = None
        
        for attempt in range(self.max_retries):
            self.stats.total_calls += 1
            
            try:
                logger.debug(f"GET {url} params={params} (attempt {attempt + 1})")
                response = self._session.get(
                    url,
                    params=params,
                    timeout=self.timeout,
                )
                
                # Parse response
                headers = dict(response.headers)
                try:
                    data = response.json()
                except ValueError:
                    data = response.text
                
                last_status = response.status_code
                last_response = data
                
                # Check if we should retry
                if self._should_retry(response.status_code):
                    retry_after = self._get_retry_after(headers)
                    backoff = self._calculate_backoff(attempt, retry_after)
                    
                    if attempt < self.max_retries - 1:
                        self.stats.retried_calls += 1
                        logger.warning(
                            f"Request failed with {response.status_code}, "
                            f"retrying in {backoff:.1f}s (attempt {attempt + 1}/{self.max_retries})"
                        )
                        time.sleep(backoff)
                        continue
                
                # Success or non-retryable error
                if response.status_code < 400:
                    self.stats.successful_calls += 1
                else:
                    self.stats.failed_calls += 1
                    
                return response.status_code, data, headers
                
            except RequestException as e:
                last_error = e
                self.stats.retried_calls += 1
                backoff = self._calculate_backoff(attempt)
                
                if attempt < self.max_retries - 1:
                    logger.warning(
                        f"Request error: {e}, retrying in {backoff:.1f}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(backoff)
                else:
                    logger.error(f"Request failed after {self.max_retries} attempts: {e}")
        
        # All retries exhausted
        self.stats.failed_calls += 1
        
        if last_error:
            raise GitLabClientError(
                f"Request failed after {self.max_retries} retries: {last_error}",
                status_code=last_status,
                response=last_response,
            )
        
        raise GitLabClientError(
            f"Request failed with status {last_status} after {self.max_retries} retries",
            status_code=last_status,
            response=last_response,
        )
    
    def paginate(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        per_page: int = DEFAULT_PER_PAGE,
        max_items: int | None = None,
    ) -> Generator[Any, None, GitLabResponse | None]:
        """
        Paginate through GitLab API results.
        
        Uses X-Next-Page header for pagination (GitLab style).
        
        Args:
            path: API endpoint path
            params: Query parameters
            per_page: Items per page (default 100, max allowed by GitLab)
            max_items: Maximum items to fetch (None for all)
            
        Yields:
            Individual items from paginated results
            
        Returns:
            Last GitLabResponse for metadata access (total counts, etc.)
        """
        params = dict(params or {})
        params["per_page"] = per_page
        page = 1
        items_fetched = 0
        last_response: GitLabResponse | None = None
        
        while True:
            params["page"] = page
            
            status_code, data, headers = self.get(path, params)
            last_response = GitLabResponse(status_code, data, headers)
            
            if not last_response.is_success:
                logger.error(f"Pagination failed at page {page}: {status_code}")
                break
            
            # Handle non-list responses
            if not isinstance(data, list):
                yield data
                break
            
            # Yield items
            for item in data:
                yield item
                items_fetched += 1
                
                if max_items is not None and items_fetched >= max_items:
                    return last_response
            
            # Check for next page
            next_page = last_response.next_page
            if not next_page:
                break
                
            page = int(next_page)
        
        return last_response
    
    def get_paginated_count(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        max_count: int | None = None,
    ) -> tuple[int, bool]:
        """
        Get count of items efficiently using pagination headers.
        
        First tries to use X-Total header (single request).
        Falls back to counting items if header not available.
        
        Args:
            path: API endpoint path
            params: Query parameters
            max_count: If counting manually, stop after this many items
            
        Returns:
            Tuple of (count, is_exact) where is_exact indicates if count is complete
        """
        params = dict(params or {})
        params["per_page"] = 1  # Minimal request to get headers
        params["page"] = 1
        
        status_code, data, headers = self.get(path, params)
        response = GitLabResponse(status_code, data, headers)
        
        if not response.is_success:
            return 0, True
        
        # Try to get total from headers
        total = response.total_items
        if total is not None:
            return total, True
        
        # Fall back to counting
        count = 0
        for _ in self.paginate(path, params, max_items=max_count):
            count += 1
        
        is_exact = max_count is None or count < max_count
        return count, is_exact
    
    def close(self) -> None:
        """Close the HTTP session."""
        self._session.close()
    
    def __enter__(self) -> "GitLabClient":
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
