"""Connections (credentials) endpoints"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List

router = APIRouter()


class ConnectionCreate(BaseModel):
    type: str  # "gitlab" or "github"
    base_url: str | None = None
    token: str


class ConnectionResponse(BaseModel):
    id: str
    type: str
    base_url: str | None
    token_last4: str
    created_at: str


@router.post("/{project_id}/connections/gitlab", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_gitlab_connection(project_id: str, connection: ConnectionCreate):
    """Add GitLab connection to project"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Connection creation not yet implemented"
    )


@router.post("/{project_id}/connections/github", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_github_connection(project_id: str, connection: ConnectionCreate):
    """Add GitHub connection to project"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Connection creation not yet implemented"
    )


@router.get("/{project_id}/connections", response_model=List[ConnectionResponse])
async def list_connections(project_id: str):
    """List all connections for a project"""
    return []
