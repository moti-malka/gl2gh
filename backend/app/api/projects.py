"""Migration projects endpoints"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.models import User
from app.services import ProjectService
from app.api.dependencies import get_current_active_user, require_operator
from app.utils.security import sanitize_project_settings

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    created_at: str
    updated_at: str
    settings: Dict[str, Any]
    status: str
    created_by: str


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project: ProjectCreate,
    current_user: User = Depends(require_operator)
):
    """Create a new migration project"""
    project_service = ProjectService()
    
    try:
        created_project = await project_service.create_project(
            name=project.name,
            created_by=str(current_user.id),
            description=project.description,
            settings=project.settings
        )
        
        return ProjectResponse(
            id=str(created_project.id),
            name=created_project.name,
            description=created_project.description,
            created_at=created_project.created_at.isoformat(),
            updated_at=created_project.updated_at.isoformat(),
            settings=sanitize_project_settings(created_project.settings.model_dump()),
            status=created_project.status,
            created_by=str(created_project.created_by)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create project: {str(e)}"
        )


@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(get_current_active_user)
):
    """List all migration projects"""
    project_service = ProjectService()
    
    # Non-admin users only see their own projects
    user_id = None if current_user.role == "admin" else str(current_user.id)
    
    projects = await project_service.list_projects(
        user_id=user_id,
        skip=skip,
        limit=limit,
        status=status_filter
    )
    
    return [
        ProjectResponse(
            id=str(p.id),
            name=p.name,
            description=p.description,
            created_at=p.created_at.isoformat(),
            updated_at=p.updated_at.isoformat(),
            settings=sanitize_project_settings(p.settings.model_dump()),
            status=p.status,
            created_by=str(p.created_by)
        )
        for p in projects
    ]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific migration project"""
    project_service = ProjectService()
    project = await project_service.get_project(project_id)
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found"
        )
    
    # Check access: admin can see all, others only their own
    if current_user.role != "admin" and str(project.created_by) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        description=project.description,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat(),
        settings=sanitize_project_settings(project.settings.model_dump()),
        status=project.status,
        created_by=str(project.created_by)
    )


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project_update: ProjectUpdate,
    current_user: User = Depends(require_operator)
):
    """Update a migration project"""
    project_service = ProjectService()
    
    # Check if project exists and user has access
    project = await project_service.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found"
        )
    
    # Check access: admin can update all, others only their own
    if current_user.role != "admin" and str(project.created_by) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Build updates dict
    updates = {}
    if project_update.name is not None:
        updates["name"] = project_update.name
    if project_update.description is not None:
        updates["description"] = project_update.description
    if project_update.settings is not None:
        updates["settings"] = project_update.settings
    
    if not updates:
        # No updates provided, return current project
        return ProjectResponse(
            id=str(project.id),
            name=project.name,
            description=project.description,
            created_at=project.created_at.isoformat(),
            updated_at=project.updated_at.isoformat(),
            settings=sanitize_project_settings(project.settings.model_dump()),
            status=project.status,
            created_by=str(project.created_by)
        )
    
    updated_project = await project_service.update_project(project_id, updates)
    if not updated_project:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update project"
        )
    
    return ProjectResponse(
        id=str(updated_project.id),
        name=updated_project.name,
        description=updated_project.description,
        created_at=updated_project.created_at.isoformat(),
        updated_at=updated_project.updated_at.isoformat(),
        settings=sanitize_project_settings(updated_project.settings.model_dump()),
        status=updated_project.status,
        created_by=str(updated_project.created_by)
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    current_user: User = Depends(require_operator)
):
    """Delete (archive) a migration project"""
    project_service = ProjectService()
    
    # Check if project exists and user has access
    project = await project_service.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found"
        )
    
    # Check access: admin can delete all, others only their own
    if current_user.role != "admin" and str(project.created_by) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    success = await project_service.delete_project(project_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete project"
        )
    
    return None
