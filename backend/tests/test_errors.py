"""Tests for enhanced error handling"""

import pytest
import httpx
from datetime import datetime, timedelta, timezone
from app.utils.errors import (
    MigrationError,
    create_gitlab_error,
    create_github_error,
    create_validation_error,
    RECOVERY_SUGGESTIONS
)


class TestMigrationError:
    """Test MigrationError dataclass"""
    
    def test_to_dict_basic(self):
        """Test conversion to dictionary without retry_after"""
        error = MigrationError(
            category="auth",
            code="TEST_001",
            message="Test error",
            technical="Technical details",
            suggestion="Fix it"
        )
        
        result = error.to_dict()
        
        assert result["category"] == "auth"
        assert result["code"] == "TEST_001"
        assert result["message"] == "Test error"
        assert result["technical"] == "Technical details"
        assert result["suggestion"] == "Fix it"
        assert "retry_after" not in result
    
    def test_to_dict_with_retry_after(self):
        """Test conversion to dictionary with retry_after"""
        retry_time = datetime.now(timezone.utc) + timedelta(seconds=60)
        error = MigrationError(
            category="rate_limit",
            code="TEST_002",
            message="Rate limited",
            technical="429 Too Many Requests",
            suggestion="Wait 1 minute",
            retry_after=retry_time
        )
        
        result = error.to_dict()
        
        assert result["retry_after"] == retry_time.isoformat()


class TestGitLabErrorCreation:
    """Test GitLab error creation"""
    
    def test_401_unauthorized(self):
        """Test 401 Unauthorized error"""
        response = httpx.Response(401, text="Unauthorized")
        exception = httpx.HTTPStatusError("401", request=None, response=response)
        
        error = create_gitlab_error(exception)
        
        assert error.category == "auth"
        assert error.code == "GITLAB_AUTH_001"
        assert "token" in error.message.lower()
        assert "expired" in error.message.lower()
        assert "api" in error.suggestion.lower()
        assert error.raw_error == exception
    
    def test_403_forbidden(self):
        """Test 403 Forbidden error"""
        response = httpx.Response(403, text="Forbidden")
        exception = httpx.HTTPStatusError("403", request=None, response=response)
        
        error = create_gitlab_error(exception, project_path="group/project")
        
        assert error.category == "permission"
        assert error.code == "GITLAB_PERMISSION_001"
        assert "group/project" in error.message
        assert "access" in error.message.lower()
        assert "permission" in error.suggestion.lower()
    
    def test_404_not_found(self):
        """Test 404 Not Found error"""
        response = httpx.Response(404, text="Not Found")
        exception = httpx.HTTPStatusError("404", request=None, response=response)
        
        error = create_gitlab_error(exception, project_path="nonexistent/repo")
        
        assert error.category == "validation"
        assert error.code == "GITLAB_NOT_FOUND_001"
        assert "nonexistent/repo" in error.message
        assert "doesn't exist" in error.message.lower()
    
    def test_429_rate_limit(self):
        """Test 429 Rate Limit error"""
        headers = {"Retry-After": "120"}
        response = httpx.Response(429, headers=headers, text="Too Many Requests")
        exception = httpx.HTTPStatusError("429", request=None, response=response)
        
        error = create_gitlab_error(exception)
        
        assert error.category == "rate_limit"
        assert error.code == "GITLAB_RATE_LIMIT_001"
        assert "rate limit" in error.message.lower()
        assert error.retry_after is not None
        assert "wait" in error.suggestion.lower()
    
    def test_500_server_error(self):
        """Test 500 Server Error"""
        response = httpx.Response(500, text="Internal Server Error")
        exception = httpx.HTTPStatusError("500", request=None, response=response)
        
        error = create_gitlab_error(exception)
        
        assert error.category == "network"
        assert error.code == "GITLAB_NETWORK_001"
        assert "server error" in error.message.lower()
    
    def test_connection_error(self):
        """Test connection error"""
        exception = httpx.ConnectError("Connection refused")
        
        error = create_gitlab_error(exception)
        
        assert error.category == "network"
        assert error.code == "GITLAB_NETWORK_001"
        assert "connect" in error.message.lower()
        assert "network" in error.suggestion.lower()
    
    def test_timeout_error(self):
        """Test timeout error"""
        exception = httpx.TimeoutException("Request timed out")
        
        error = create_gitlab_error(exception)
        
        assert error.category == "network"
        assert error.code == "GITLAB_TIMEOUT_001"
        assert "timeout" in error.message.lower()
    
    def test_generic_error(self):
        """Test generic error fallback"""
        exception = Exception("Something went wrong")
        
        error = create_gitlab_error(exception)
        
        assert error.category == "unknown"
        assert error.code == "GITLAB_ERROR_999"
        assert "unexpected" in error.message.lower()


class TestGitHubErrorCreation:
    """Test GitHub error creation"""
    
    def test_401_unauthorized(self):
        """Test 401 Unauthorized error"""
        response = httpx.Response(401, text="Unauthorized")
        exception = httpx.HTTPStatusError("401", request=None, response=response)
        
        error = create_github_error(exception)
        
        assert error.category == "auth"
        assert error.code == "GITHUB_AUTH_001"
        assert "token" in error.message.lower()
        assert "repo" in error.suggestion.lower()
        assert "workflow" in error.suggestion.lower()
    
    def test_403_rate_limit(self):
        """Test 403 Rate Limit error"""
        headers = {"X-RateLimit-Reset": str(int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()))}
        response = httpx.Response(403, headers=headers, text="rate limit exceeded")
        exception = httpx.HTTPStatusError("403", request=None, response=response)
        
        error = create_github_error(exception)
        
        assert error.category == "rate_limit"
        assert error.code == "GITHUB_RATE_001"
        assert "rate limit" in error.message.lower()
        assert error.retry_after is not None
    
    def test_403_permission(self):
        """Test 403 Permission error"""
        response = httpx.Response(403, text="Forbidden")
        exception = httpx.HTTPStatusError("403", request=None, response=response)
        
        error = create_github_error(exception, resource="organization/repo")
        
        assert error.category == "permission"
        assert error.code == "GITHUB_PERMISSION_001"
        assert "organization/repo" in error.message
    
    def test_404_not_found(self):
        """Test 404 Not Found error"""
        response = httpx.Response(404, text="Not Found")
        exception = httpx.HTTPStatusError("404", request=None, response=response)
        
        error = create_github_error(exception, resource="org/repo")
        
        assert error.category == "validation"
        assert error.code == "GITHUB_NOT_FOUND_001"
        assert "org/repo" in error.message


class TestValidationError:
    """Test validation error creation"""
    
    def test_create_validation_error(self):
        """Test creating a validation error"""
        error = create_validation_error(
            message="Invalid input format",
            technical="Expected JSON, got plain text"
        )
        
        assert error.category == "validation"
        assert error.code == "VALIDATION_001"
        assert error.message == "Invalid input format"
        assert error.technical == "Expected JSON, got plain text"
        assert "validation" in error.suggestion.lower()


class TestRecoverySuggestions:
    """Test recovery suggestions mapping"""
    
    def test_gitlab_auth_suggestions(self):
        """Test GitLab auth suggestions exist"""
        assert "GITLAB_AUTH_001" in RECOVERY_SUGGESTIONS
        suggestions = RECOVERY_SUGGESTIONS["GITLAB_AUTH_001"]
        assert len(suggestions) > 0
        assert any("token" in s.lower() for s in suggestions)
    
    def test_github_rate_suggestions(self):
        """Test GitHub rate limit suggestions exist"""
        assert "GITHUB_RATE_001" in RECOVERY_SUGGESTIONS
        suggestions = RECOVERY_SUGGESTIONS["GITHUB_RATE_001"]
        assert len(suggestions) > 0
        assert any("{wait_time}" in s for s in suggestions)
    
    def test_validation_suggestions(self):
        """Test validation suggestions exist"""
        assert "VALIDATION_001" in RECOVERY_SUGGESTIONS
        suggestions = RECOVERY_SUGGESTIONS["VALIDATION_001"]
        assert len(suggestions) > 0
