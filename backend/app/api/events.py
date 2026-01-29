"""Events and logs endpoints"""

from fastapi import APIRouter, Query, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.models import User
from app.services import EventService, RunService, ProjectService
from app.api.dependencies import require_operator

router = APIRouter()


class EventResponse(BaseModel):
    id: str
    run_id: str
    timestamp: str
    level: str
    agent: Optional[str]
    scope: str
    gitlab_project_id: Optional[int]
    message: str
    payload: Dict[str, Any]


async def check_run_access(run_id: str, current_user: User):
    """Check if user has access to run"""
    run_service = RunService()
    run = await run_service.get_run(run_id)
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found"
        )
    
    # Check project access
    project_service = ProjectService()
    project = await project_service.get_project(str(run.project_id))
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Check access: admin can see all, others only their own
    if current_user.role != "admin" and str(project.created_by) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return run


@router.get("/{run_id}/events", response_model=List[EventResponse])
async def get_run_events(
    run_id: str,
    level: Optional[str] = Query(None, description="Filter by level (INFO, WARN, ERROR, DEBUG)"),
    agent: Optional[str] = Query(None, description="Filter by agent name"),
    scope: Optional[str] = Query(None, description="Filter by scope (run, project)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(require_operator)
):
    """Get events for a run with pagination and filtering"""
    await check_run_access(run_id, current_user)
    
    event_service = EventService()
    events = await event_service.get_events(
        run_id=run_id,
        skip=skip,
        limit=limit,
        level_filter=level,
        agent_filter=agent,
        scope_filter=scope
    )
    
    return [
        EventResponse(
            id=str(e.id),
            run_id=str(e.run_id),
            timestamp=e.timestamp.isoformat(),
            level=e.level,
            agent=e.agent,
            scope=e.scope,
            gitlab_project_id=e.gitlab_project_id,
            message=e.message,
            payload=e.payload
        )
        for e in events
    ]


@router.get("/{run_id}/projects")
async def get_run_projects(
    run_id: str,
    current_user: User = Depends(require_operator)
):
    """Get all projects in a run"""
    await check_run_access(run_id, current_user)
    
    # TODO: Implement run_projects collection query
    return {"projects": [], "message": "Run projects listing not yet implemented"}


@router.get("/{run_id}/projects/{gitlab_project_id}")
async def get_run_project(
    run_id: str,
    gitlab_project_id: int,
    current_user: User = Depends(require_operator)
):
    """Get details for a specific project in a run"""
    await check_run_access(run_id, current_user)
    
    # TODO: Implement run_projects collection query
    return {
        "run_id": run_id,
        "gitlab_project_id": gitlab_project_id,
        "message": "Project details not yet implemented"
    }
