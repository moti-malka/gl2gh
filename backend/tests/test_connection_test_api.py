"""Tests for connection test API endpoints"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from bson import ObjectId


@pytest.mark.asyncio
async def test_test_gitlab_connection_valid():
    """Test GitLab connection test with valid token"""
    from app.api.connections import test_gitlab_connection, GitLabTestRequest
    
    # Mock user and project for access control
    mock_user = MagicMock()
    mock_user.id = ObjectId()
    mock_user.role = "operator"
    
    mock_project_id = str(ObjectId())
    
    # Mock check_project_access
    with patch("app.api.connections.check_project_access", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = None
        
        # Mock GitLab client
        mock_user_info = {
            "username": "test-user",
            "id": 123,
            "email": "test@example.com"
        }
        
        with patch("app.api.connections.GitLabClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get_current_user = AsyncMock(return_value=mock_user_info)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client
            
            request = GitLabTestRequest(
                token="glpat-test-token",
                base_url="https://gitlab.com"
            )
            
            response = await test_gitlab_connection(
                project_id=mock_project_id,
                request=request,
                current_user=mock_user
            )
            
            assert response.valid is True
            assert response.user == "test-user"
            assert response.error is None


@pytest.mark.asyncio
async def test_test_gitlab_connection_invalid_token():
    """Test GitLab connection test with invalid token"""
    from app.api.connections import test_gitlab_connection, GitLabTestRequest
    
    mock_user = MagicMock()
    mock_user.id = ObjectId()
    mock_user.role = "operator"
    mock_project_id = str(ObjectId())
    
    with patch("app.api.connections.check_project_access", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = None
        
        with patch("app.api.connections.GitLabClient") as mock_client_class:
            mock_client = AsyncMock()
            
            # Simulate 401 error
            mock_response = AsyncMock()
            mock_response.status_code = 401
            error = httpx.HTTPStatusError("Unauthorized", request=AsyncMock(), response=mock_response)
            mock_client.get_current_user = AsyncMock(side_effect=error)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client
            
            request = GitLabTestRequest(
                token="invalid-token",
                base_url="https://gitlab.com"
            )
            
            response = await test_gitlab_connection(
                project_id=mock_project_id,
                request=request,
                current_user=mock_user
            )
            
            assert response.valid is False
            assert response.error == "Invalid token or insufficient permissions"
            assert response.user is None


@pytest.mark.asyncio
async def test_test_gitlab_connection_network_error():
    """Test GitLab connection test with network error"""
    from app.api.connections import test_gitlab_connection, GitLabTestRequest
    
    mock_user = MagicMock()
    mock_user.id = ObjectId()
    mock_user.role = "operator"
    mock_project_id = str(ObjectId())
    
    with patch("app.api.connections.check_project_access", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = None
        
        with patch("app.api.connections.GitLabClient") as mock_client_class:
            mock_client = AsyncMock()
            
            # Simulate network error
            error = httpx.RequestError("Connection timeout")
            mock_client.get_current_user = AsyncMock(side_effect=error)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client
            
            request = GitLabTestRequest(
                token="glpat-test-token",
                base_url="https://gitlab.com"
            )
            
            response = await test_gitlab_connection(
                project_id=mock_project_id,
                request=request,
                current_user=mock_user
            )
            
            assert response.valid is False
            assert "Connection failed" in response.error


@pytest.mark.asyncio
async def test_test_github_connection_valid():
    """Test GitHub connection test with valid token"""
    from app.api.connections import test_github_connection, GitHubTestRequest
    
    mock_user = MagicMock()
    mock_user.id = ObjectId()
    mock_user.role = "operator"
    mock_project_id = str(ObjectId())
    
    # Mock GitHub API response
    mock_response_data = {
        "login": "test-user",
        "id": 123,
        "type": "User"
    }
    
    mock_headers = {
        "X-RateLimit-Remaining": "4999",
        "X-RateLimit-Reset": "1234567890"
    }
    
    with patch("app.api.connections.check_project_access", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = None
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()  # Use MagicMock for non-async response object
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_response.headers = mock_headers
            
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client
            
            request = GitHubTestRequest(token="ghp_test_token")
            
            response = await test_github_connection(
                project_id=mock_project_id,
                request=request,
                current_user=mock_user
            )
            
            assert response.valid is True
            assert response.user == "test-user"
            assert response.type == "user"
            assert response.rate_limit is not None
            assert response.rate_limit["remaining"] == 4999
            assert response.error is None


@pytest.mark.asyncio
async def test_test_github_connection_organization():
    """Test GitHub connection test with organization account"""
    from app.api.connections import test_github_connection, GitHubTestRequest
    
    mock_user = MagicMock()
    mock_user.id = ObjectId()
    mock_user.role = "operator"
    mock_project_id = str(ObjectId())
    
    # Mock GitHub API response for organization
    mock_response_data = {
        "login": "test-org",
        "id": 456,
        "type": "Organization"
    }
    
    with patch("app.api.connections.check_project_access", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = None
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()  # Use MagicMock for non-async response object
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_response.headers = {}
            
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client
            
            request = GitHubTestRequest(token="ghp_test_token")
            
            response = await test_github_connection(
                project_id=mock_project_id,
                request=request,
                current_user=mock_user
            )
            
            assert response.valid is True
            assert response.user == "test-org"
            assert response.type == "organization"


@pytest.mark.asyncio
async def test_test_github_connection_invalid_token():
    """Test GitHub connection test with invalid token"""
    from app.api.connections import test_github_connection, GitHubTestRequest
    
    mock_user = MagicMock()
    mock_user.id = ObjectId()
    mock_user.role = "operator"
    mock_project_id = str(ObjectId())
    
    with patch("app.api.connections.check_project_access", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = None
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 401
            
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client
            
            request = GitHubTestRequest(token="invalid_token")
            
            response = await test_github_connection(
                project_id=mock_project_id,
                request=request,
                current_user=mock_user
            )
            
            assert response.valid is False
            assert response.error == "Invalid token or token has expired"
            assert response.user is None


@pytest.mark.asyncio
async def test_test_github_connection_insufficient_permissions():
    """Test GitHub connection test with insufficient permissions"""
    from app.api.connections import test_github_connection, GitHubTestRequest
    
    mock_user = MagicMock()
    mock_user.id = ObjectId()
    mock_user.role = "operator"
    mock_project_id = str(ObjectId())
    
    with patch("app.api.connections.check_project_access", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = None
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 403
            
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client
            
            request = GitHubTestRequest(token="ghp_limited_token")
            
            response = await test_github_connection(
                project_id=mock_project_id,
                request=request,
                current_user=mock_user
            )
            
            assert response.valid is False
            assert response.error == "Token does not have required permissions"


@pytest.mark.asyncio
async def test_test_github_connection_network_error():
    """Test GitHub connection test with network error"""
    from app.api.connections import test_github_connection, GitHubTestRequest
    
    mock_user = MagicMock()
    mock_user.id = ObjectId()
    mock_user.role = "operator"
    mock_project_id = str(ObjectId())
    
    with patch("app.api.connections.check_project_access", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = None
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            
            # Simulate network error
            error = httpx.RequestError("Connection timeout")
            mock_client.get = AsyncMock(side_effect=error)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client
            
            request = GitHubTestRequest(token="ghp_test_token")
            
            response = await test_github_connection(
                project_id=mock_project_id,
                request=request,
                current_user=mock_user
            )
            
            assert response.valid is False
            assert "Connection failed" in response.error

