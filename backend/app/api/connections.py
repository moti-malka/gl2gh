"""Connections (credentials) endpoints"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import List, Optional

from app.models import User
from app.services import ConnectionService
from app.api.dependencies import require_operator
from app.api.utils import check_project_access
from app.clients.gitlab_client import GitLabClient
import httpx

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


class ConnectionTestRequest(BaseModel):
    base_url: str
    token: str


class ConnectionTestResponse(BaseModel):
    success: bool
    user: Optional[str] = None
    scopes: Optional[List[str]] = None
    message: Optional[str] = None


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


@router.post("/connections/test/gitlab", response_model=ConnectionTestResponse)
async def test_gitlab_connection(
    request: ConnectionTestRequest,
    current_user: User = Depends(require_operator)
):
    """Test GitLab connection without saving it"""
    try:
        # Use default GitLab URL if not provided
        base_url = request.base_url or "https://gitlab.com"
        
        # Create GitLab client and test connection
        async with GitLabClient(base_url=base_url, token=request.token, timeout=10) as client:
            # Try to get current user information
            response = await client._request("GET", "/user")
            user_data = response.json()
            
            # Extract username
            username = user_data.get("username")
            
            # Get token scopes from response headers
            scopes = None
            if "X-Oauth-Scopes" in response.headers:
                scopes = [s.strip() for s in response.headers["X-Oauth-Scopes"].split(",")]
            
            return ConnectionTestResponse(
                success=True,
                user=username,
                scopes=scopes,
                message="Connection successful"
            )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return ConnectionTestResponse(
                success=False,
                message="Invalid token or insufficient permissions"
            )
        else:
            return ConnectionTestResponse(
                success=False,
                message=f"GitLab API error: {e.response.status_code}"
            )
    except httpx.RequestError as e:
        return ConnectionTestResponse(
            success=False,
            message=f"Connection error: Unable to reach GitLab server"
        )
    except Exception as e:
        return ConnectionTestResponse(
            success=False,
            message=f"Unexpected error: {str(e)}"
        )


@router.post("/connections/test/github", response_model=ConnectionTestResponse)
async def test_github_connection(
    request: ConnectionTestRequest,
    current_user: User = Depends(require_operator)
):
    """Test GitHub connection without saving it"""
    try:
        # Use default GitHub API URL if not provided
        base_url = request.base_url or "https://api.github.com"
        
        # Create HTTP client and test connection
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{base_url}/user",
                headers={
                    "Authorization": f"token {request.token}",
                    "Accept": "application/vnd.github.v3+json"
                }
            )
            response.raise_for_status()
            user_data = response.json()
            
            # Extract username (login)
            username = user_data.get("login")
            
            # Get token scopes from response headers
            scopes = None
            if "X-OAuth-Scopes" in response.headers:
                scopes = [s.strip() for s in response.headers["X-OAuth-Scopes"].split(",") if s.strip()]
            
            return ConnectionTestResponse(
                success=True,
                user=username,
                scopes=scopes,
                message="Connection successful"
            )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return ConnectionTestResponse(
                success=False,
                message="Invalid token or insufficient permissions"
            )
        else:
            return ConnectionTestResponse(
                success=False,
                message=f"GitHub API error: {e.response.status_code}"
            )
    except httpx.RequestError as e:
        return ConnectionTestResponse(
            success=False,
            message=f"Connection error: Unable to reach GitHub server"
        )
    except Exception as e:
        return ConnectionTestResponse(
            success=False,
            message=f"Unexpected error: {str(e)}"
        )
