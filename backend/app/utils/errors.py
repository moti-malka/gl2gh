"""Enhanced error handling with actionable suggestions"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import httpx


@dataclass
class MigrationError:
    """
    Structured error with user-friendly messaging and recovery suggestions.
    
    Attributes:
        category: Error category (auth, permission, rate_limit, network, validation)
        code: Unique error code (e.g., "GITLAB_AUTH_001")
        message: User-friendly error message
        technical: Technical details for debugging
        suggestion: What the user should do to fix it
        retry_after: Optional timestamp when the operation can be retried
        raw_error: Original exception for logging
    """
    category: str
    code: str
    message: str
    technical: str
    suggestion: str
    retry_after: Optional[datetime] = None
    raw_error: Optional[Exception] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for serialization"""
        result = {
            "category": self.category,
            "code": self.code,
            "message": self.message,
            "technical": self.technical,
            "suggestion": self.suggestion
        }
        if self.retry_after:
            result["retry_after"] = self.retry_after.isoformat()
        return result


# Error code to recovery suggestions mapping
RECOVERY_SUGGESTIONS = {
    "GITLAB_AUTH_001": [
        "Check your GitLab token hasn't expired",
        "Regenerate token with 'api' scope",
        "Ensure token has access to the project"
    ],
    "GITLAB_AUTH_002": [
        "Verify the GitLab token is valid",
        "Ensure the token has not been revoked",
        "Generate a new Personal Access Token with 'api' scope"
    ],
    "GITLAB_PERMISSION_001": [
        "Request access to the project or group",
        "Use a token with appropriate permissions",
        "Verify you have at least 'Developer' role for the project"
    ],
    "GITLAB_NOT_FOUND_001": [
        "Check the project path is correct (format: group/project)",
        "Verify the project exists in GitLab",
        "Ensure you have access to view the project"
    ],
    "GITLAB_RATE_LIMIT_001": [
        "Wait {wait_time} before retrying",
        "Use a token with higher rate limits",
        "Consider using GitLab Premium for higher limits"
    ],
    "GITLAB_NETWORK_001": [
        "Check your GitLab instance URL is correct",
        "Verify network connectivity to GitLab",
        "Check if GitLab is behind a firewall or VPN"
    ],
    "GITLAB_TIMEOUT_001": [
        "Try again later",
        "Check if the repository is very large",
        "Consider increasing timeout settings"
    ],
    "GITHUB_AUTH_001": [
        "Verify your GitHub token is valid",
        "Regenerate token with required scopes: repo, workflow, admin:org",
        "Ensure token has not expired"
    ],
    "GITHUB_PERMISSION_001": [
        "Verify token has admin access to the target organization",
        "Check that the organization settings allow token access",
        "Use a token from an organization owner"
    ],
    "GITHUB_RATE_001": [
        "Wait {wait_time} before retrying",
        "Use a GitHub App for higher limits (5000 req/hour)",
        "Enable checkpoint resume to continue later"
    ],
    "VALIDATION_001": [
        "Review the validation errors in the technical details",
        "Ensure all required fields are provided",
        "Check that the input format matches the expected schema"
    ]
}


def create_gitlab_error(exception: Exception, project_path: Optional[str] = None) -> MigrationError:
    """
    Create a MigrationError from a GitLab API exception with user-friendly message.
    
    Args:
        exception: The original exception
        project_path: Optional project path for context
        
    Returns:
        MigrationError with appropriate category and suggestions
    """
    if isinstance(exception, httpx.HTTPStatusError):
        status_code = exception.response.status_code
        
        # 401 Unauthorized
        if status_code == 401:
            return MigrationError(
                category="auth",
                code="GITLAB_AUTH_001",
                message="Invalid or expired GitLab token",
                technical=f"HTTP 401 Unauthorized: {str(exception)}",
                suggestion="Generate a new GitLab Personal Access Token with 'api' scope and ensure it hasn't expired. "
                           "Go to GitLab → User Settings → Access Tokens to create one.",
                raw_error=exception
            )
        
        # 403 Forbidden
        elif status_code == 403:
            project_msg = f" for project '{project_path}'" if project_path else ""
            return MigrationError(
                category="permission",
                code="GITLAB_PERMISSION_001",
                message=f"No access to GitLab resource{project_msg}",
                technical=f"HTTP 403 Forbidden: {str(exception)}",
                suggestion=f"The GitLab token doesn't have access{project_msg}. "
                           "Request access to the project/group or use a different token with appropriate permissions. "
                           "Required scope: 'api' or 'read_repository'",
                raw_error=exception
            )
        
        # 404 Not Found
        elif status_code == 404:
            project_msg = f" '{project_path}'" if project_path else ""
            return MigrationError(
                category="validation",
                code="GITLAB_NOT_FOUND_001",
                message=f"GitLab project{project_msg} doesn't exist",
                technical=f"HTTP 404 Not Found: {str(exception)}",
                suggestion="Check the project URL/path is correct (format: group/project). "
                           "Verify the project exists and you have permission to view it.",
                raw_error=exception
            )
        
        # 429 Rate Limited
        elif status_code == 429:
            retry_after = int(exception.response.headers.get('Retry-After', 60))
            retry_time = datetime.utcnow() + timedelta(seconds=retry_after)
            wait_minutes = retry_after // 60
            wait_seconds = retry_after % 60
            
            wait_time_str = ""
            if wait_minutes > 0:
                wait_time_str = f"{wait_minutes} minute{'s' if wait_minutes > 1 else ''}"
                if wait_seconds > 0:
                    wait_time_str += f" {wait_seconds} seconds"
            else:
                wait_time_str = f"{wait_seconds} seconds"
            
            suggestions = [s.format(wait_time=wait_time_str) for s in RECOVERY_SUGGESTIONS["GITLAB_RATE_LIMIT_001"]]
            
            return MigrationError(
                category="rate_limit",
                code="GITLAB_RATE_LIMIT_001",
                message=f"GitLab rate limit exceeded",
                technical=f"HTTP 429 Too Many Requests: {str(exception)}",
                suggestion=f"Rate limit exceeded. {suggestions[0]}. {suggestions[1]}",
                retry_after=retry_time,
                raw_error=exception
            )
        
        # 500+ Server Errors
        elif status_code >= 500:
            return MigrationError(
                category="network",
                code="GITLAB_NETWORK_001",
                message="GitLab server error",
                technical=f"HTTP {status_code} Server Error: {str(exception)}",
                suggestion="GitLab is experiencing issues. Try again in a few minutes. "
                           "If the problem persists, check GitLab's status page.",
                raw_error=exception
            )
    
    # Network/Connection errors
    elif isinstance(exception, (httpx.ConnectError, httpx.ConnectTimeout)):
        return MigrationError(
            category="network",
            code="GITLAB_NETWORK_001",
            message="Cannot connect to GitLab",
            technical=f"Connection error: {str(exception)}",
            suggestion="Check the GitLab URL is correct and that GitLab is accessible. "
                       "Verify your network connection and that GitLab is not behind a firewall.",
            raw_error=exception
        )
    
    # Timeout errors
    elif isinstance(exception, httpx.TimeoutException):
        return MigrationError(
            category="network",
            code="GITLAB_TIMEOUT_001",
            message="GitLab request timed out",
            technical=f"Timeout error: {str(exception)}",
            suggestion="The request took too long. This may happen with large repositories. "
                       "Try again, or consider increasing the timeout setting.",
            raw_error=exception
        )
    
    # Generic error fallback
    return MigrationError(
        category="unknown",
        code="GITLAB_ERROR_999",
        message="An unexpected error occurred",
        technical=f"{type(exception).__name__}: {str(exception)}",
        suggestion="Review the technical details for more information. "
                   "If the problem persists, contact support with the error details.",
        raw_error=exception
    )


def create_github_error(exception: Exception, resource: Optional[str] = None) -> MigrationError:
    """
    Create a MigrationError from a GitHub API exception with user-friendly message.
    
    Args:
        exception: The original exception
        resource: Optional resource description for context
        
    Returns:
        MigrationError with appropriate category and suggestions
    """
    if isinstance(exception, httpx.HTTPStatusError):
        status_code = exception.response.status_code
        
        # 401 Unauthorized
        if status_code == 401:
            return MigrationError(
                category="auth",
                code="GITHUB_AUTH_001",
                message="Invalid or expired GitHub token",
                technical=f"HTTP 401 Unauthorized: {str(exception)}",
                suggestion="Generate a new GitHub Personal Access Token with required scopes: "
                           "'repo', 'workflow', 'admin:org'. Go to GitHub → Settings → Developer settings → "
                           "Personal access tokens to create one.",
                raw_error=exception
            )
        
        # 403 Forbidden (often rate limiting or permissions)
        elif status_code == 403:
            # Check if it's rate limiting
            if 'rate limit' in str(exception).lower():
                retry_after = int(exception.response.headers.get('X-RateLimit-Reset', 0))
                if retry_after:
                    retry_time = datetime.fromtimestamp(retry_after)
                    wait_seconds = max(0, (retry_time - datetime.utcnow()).total_seconds())
                    wait_minutes = int(wait_seconds // 60)
                    
                    wait_time_str = f"{wait_minutes} minutes" if wait_minutes > 0 else f"{int(wait_seconds)} seconds"
                    suggestions = [s.format(wait_time=wait_time_str) for s in RECOVERY_SUGGESTIONS["GITHUB_RATE_001"]]
                    
                    return MigrationError(
                        category="rate_limit",
                        code="GITHUB_RATE_001",
                        message=f"GitHub API rate limit exceeded",
                        technical=f"HTTP 403 Rate Limited: {str(exception)}",
                        suggestion=suggestions[0] if suggestions else "Wait before retrying",
                        retry_after=retry_time,
                        raw_error=exception
                    )
            
            # Permission error
            resource_msg = f" for {resource}" if resource else ""
            return MigrationError(
                category="permission",
                code="GITHUB_PERMISSION_001",
                message=f"No access to GitHub resource{resource_msg}",
                technical=f"HTTP 403 Forbidden: {str(exception)}",
                suggestion="The GitHub token doesn't have sufficient permissions. "
                           "Ensure the token has 'repo', 'workflow', and 'admin:org' scopes, "
                           "and that you have admin access to the target organization.",
                raw_error=exception
            )
        
        # 404 Not Found
        elif status_code == 404:
            resource_msg = f" '{resource}'" if resource else ""
            return MigrationError(
                category="validation",
                code="GITHUB_NOT_FOUND_001",
                message=f"GitHub resource{resource_msg} not found",
                technical=f"HTTP 404 Not Found: {str(exception)}",
                suggestion="Check that the organization/repository name is correct and that you have access to it.",
                raw_error=exception
            )
    
    # Network/Connection errors
    elif isinstance(exception, (httpx.ConnectError, httpx.ConnectTimeout)):
        return MigrationError(
            category="network",
            code="GITHUB_NETWORK_001",
            message="Cannot connect to GitHub",
            technical=f"Connection error: {str(exception)}",
            suggestion="Check your network connection to GitHub. Verify that GitHub is accessible and not blocked by a firewall.",
            raw_error=exception
        )
    
    # Timeout errors
    elif isinstance(exception, httpx.TimeoutException):
        return MigrationError(
            category="network",
            code="GITHUB_TIMEOUT_001",
            message="GitHub request timed out",
            technical=f"Timeout error: {str(exception)}",
            suggestion="The request took too long. Try again later.",
            raw_error=exception
        )
    
    # Generic error fallback
    return MigrationError(
        category="unknown",
        code="GITHUB_ERROR_999",
        message="An unexpected error occurred",
        technical=f"{type(exception).__name__}: {str(exception)}",
        suggestion="Review the technical details for more information.",
        raw_error=exception
    )


def create_validation_error(message: str, technical: str) -> MigrationError:
    """
    Create a validation error.
    
    Args:
        message: User-friendly message
        technical: Technical details
        
    Returns:
        MigrationError for validation issues
    """
    return MigrationError(
        category="validation",
        code="VALIDATION_001",
        message=message,
        technical=technical,
        suggestion="Review the validation errors and ensure all required fields are provided with correct formats.",
        raw_error=None
    )
