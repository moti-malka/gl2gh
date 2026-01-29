"""Connections (credentials) endpoints"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import List, Optional

from app.models import User
from app.services import ConnectionService
from app.api.dependencies import require_operator
from app.api.utils import check_project_access

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
