"""Connections (credentials) endpoints"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import httpx

from app.models import User
from app.services import ConnectionService
from app.api.dependencies import require_operator
from app.api.utils import check_project_access
from app.clients.gitlab_client import GitLabClient

router = APIRouter()


class ConnectionCreate(BaseModel):
    type: str  # "gitlab" or "github"
    base_url: Optional[str] = None
    token: str


class ConnectionResponse(BaseModel):
    id: str
    type: str
    base_url: Optional[str]
    token_last4: str
    created_at: str


class GitLabTestRequest(BaseModel):
    token: str
    base_url: Optional[str] = "https://gitlab.com"


class GitHubTestRequest(BaseModel):
    token: str


class GitLabTestResponse(BaseModel):
    valid: bool
    user: Optional[str] = None
    scopes: List[str] = []
    expires_at: Optional[str] = None
    error: Optional[str] = None


class GitHubTestResponse(BaseModel):
    valid: bool
    user: Optional[str] = None
    type: Optional[str] = None
    rate_limit: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@router.post("/{project_id}/connections/gitlab", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_gitlab_connection(
    project_id: str,
    connection: ConnectionCreate,
    current_user: User = Depends(require_operator)
):
    """Add GitLab connection to project"""
    await check_project_access(project_id, current_user)
    
    connection_service = ConnectionService()
    
    try:
        conn = await connection_service.store_gitlab_connection(
            project_id=project_id,
            token=connection.token,
            base_url=connection.base_url
        )
        
        return ConnectionResponse(
            id=str(conn.id),
            type=conn.type,
            base_url=conn.base_url,
            token_last4=conn.token_last4,
            created_at=conn.created_at.isoformat()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create connection: {str(e)}"
        )


@router.post("/{project_id}/connections/github", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_github_connection(
    project_id: str,
    connection: ConnectionCreate,
    current_user: User = Depends(require_operator)
):
    """Add GitHub connection to project"""
    await check_project_access(project_id, current_user)
    
    connection_service = ConnectionService()
    
    try:
        conn = await connection_service.store_github_connection(
            project_id=project_id,
            token=connection.token,
            base_url=connection.base_url
        )
        
        return ConnectionResponse(
            id=str(conn.id),
            type=conn.type,
            base_url=conn.base_url,
            token_last4=conn.token_last4,
            created_at=conn.created_at.isoformat()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create connection: {str(e)}"
        )


@router.get("/{project_id}/connections", response_model=List[ConnectionResponse])
async def list_connections(
    project_id: str,
    current_user: User = Depends(require_operator)
):
    """List all connections for a project"""
    await check_project_access(project_id, current_user)
    
    connection_service = ConnectionService()
    connections = await connection_service.get_connections(project_id)
    
    return [
        ConnectionResponse(
            id=str(c.id),
            type=c.type,
            base_url=c.base_url,
            token_last4=c.token_last4,
            created_at=c.created_at.isoformat()
        )
        for c in connections
    ]


@router.delete("/{project_id}/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    project_id: str,
    connection_id: str,
    current_user: User = Depends(require_operator)
):
    """Delete a connection"""
    await check_project_access(project_id, current_user)
    
    connection_service = ConnectionService()
    success = await connection_service.delete_connection(connection_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found"
        )
    
    return None


@router.post("/{project_id}/connections/gitlab/test", response_model=GitLabTestResponse)
async def test_gitlab_connection(
    project_id: str,
    request: GitLabTestRequest,
    current_user: User = Depends(require_operator)
):
    """
    Test GitLab connection by validating the token against GitLab API.
    
    Args:
        project_id: Project ID (used for access control)
        request: GitLab test request containing token and base_url
        current_user: Current authenticated user
        
    Returns:
        GitLabTestResponse with validation results
    """
    await check_project_access(project_id, current_user)
    
    try:
        # Initialize GitLab client with provided credentials
        base_url = request.base_url or "https://gitlab.com"
        
        async with GitLabClient(base_url, request.token) as client:
            # Test connection by getting current user
            user_info = await client.get_current_user()
            
            # Extract scopes from token (if available in headers)
            # Note: GitLab doesn't provide scopes in the user response,
            # but we can infer successful API access
            scopes = []
            
            return GitLabTestResponse(
                valid=True,
                user=user_info.get("username"),
                scopes=scopes,
                expires_at=None  # GitLab tokens don't have expiration in API response
            )
            
    except httpx.HTTPStatusError as e:
        # Handle HTTP errors (e.g., 401 Unauthorized, 403 Forbidden)
        error_detail = f"HTTP {e.response.status_code}"
        if e.response.status_code == 401:
            error_detail = "Invalid token or insufficient permissions"
        elif e.response.status_code == 403:
            error_detail = "Token does not have required scopes"
        
        return GitLabTestResponse(
            valid=False,
            error=error_detail
        )
        
    except httpx.RequestError as e:
        # Handle network errors
        return GitLabTestResponse(
            valid=False,
            error=f"Connection failed: {str(e)}"
        )
        
    except Exception as e:
        # Handle other errors
        return GitLabTestResponse(
            valid=False,
            error=f"Unexpected error: {str(e)}"
        )


@router.post("/{project_id}/connections/github/test", response_model=GitHubTestResponse)
async def test_github_connection(
    project_id: str,
    request: GitHubTestRequest,
    current_user: User = Depends(require_operator)
):
    """
    Test GitHub connection by validating the token against GitHub API.
    
    Args:
        project_id: Project ID (used for access control)
        request: GitHub test request containing token
        current_user: Current authenticated user
        
    Returns:
        GitHubTestResponse with validation results
    """
    await check_project_access(project_id, current_user)
    
    try:
        # Test connection using GitHub API /user endpoint
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {request.token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                },
                timeout=10.0
            )
            
            if response.status_code == 200:
                user_data = response.json()
                
                # Extract rate limit information from headers
                rate_limit_info = None
                if "X-RateLimit-Remaining" in response.headers:
                    rate_limit_info = {
                        "remaining": int(response.headers.get("X-RateLimit-Remaining", 0)),
                        "reset_at": response.headers.get("X-RateLimit-Reset", None)
                    }
                
                # Determine if user or organization
                account_type = "organization" if user_data.get("type") == "Organization" else "user"
                
                return GitHubTestResponse(
                    valid=True,
                    user=user_data.get("login"),
                    type=account_type,
                    rate_limit=rate_limit_info
                )
            else:
                # Handle non-200 responses
                error_detail = f"HTTP {response.status_code}"
                if response.status_code == 401:
                    error_detail = "Invalid token or token has expired"
                elif response.status_code == 403:
                    error_detail = "Token does not have required permissions"
                
                return GitHubTestResponse(
                    valid=False,
                    error=error_detail
                )
                
    except httpx.RequestError as e:
        # Handle network errors
        return GitHubTestResponse(
            valid=False,
            error=f"Connection failed: {str(e)}"
        )
        
    except Exception as e:
        # Handle other errors
        return GitHubTestResponse(
            valid=False,
            error=f"Unexpected error: {str(e)}"
        )

