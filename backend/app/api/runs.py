"""Migration runs endpoints"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.models import User
from app.services import RunService, ArtifactService
from app.api.dependencies import require_operator
from app.api.utils import check_project_access, check_run_access

router = APIRouter()


class RunCreate(BaseModel):
    mode: str = "PLAN_ONLY"
    deep: bool = False
    deep_top_n: int = 20
    filters: Optional[Dict[str, Any]] = None


class ResumeRequest(BaseModel):
    from_stage: Optional[str] = None


class RunResponse(BaseModel):
    id: str
    project_id: str
    mode: str
    status: str
    stage: Optional[str]
    started_at: Optional[str]
    finished_at: Optional[str]
    stats: Dict[str, int]
    error: Optional[Dict[str, str]]


class ArtifactResponse(BaseModel):
    id: str
    type: str
    path: str
    size_bytes: Optional[int]
    created_at: str
    metadata: Dict[str, Any]


@router.post("/projects/{project_id}/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    project_id: str,
    run: RunCreate,
    current_user: User = Depends(require_operator)
):
    """Create and start a new migration run"""
    await check_project_access(project_id, current_user)
    
    run_service = RunService()
    
    try:
        # Create config snapshot
        config = {
            "deep": run.deep,
            "deep_top_n": run.deep_top_n,
            "filters": run.filters or {}
        }
        
        created_run = await run_service.create_run(
            project_id=project_id,
            mode=run.mode,
            config=config
        )
        
        return RunResponse(
            id=str(created_run.id),
            project_id=str(created_run.project_id),
            mode=created_run.mode,
            status=created_run.status,
            stage=created_run.stage,
            started_at=created_run.started_at.isoformat() if created_run.started_at else None,
            finished_at=created_run.finished_at.isoformat() if created_run.finished_at else None,
            stats=created_run.stats.model_dump(),
            error=created_run.error
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create run: {str(e)}"
        )


@router.get("/projects/{project_id}/runs", response_model=List[RunResponse])
async def list_project_runs(
    project_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(require_operator)
):
    """List all runs for a project"""
    await check_project_access(project_id, current_user)
    
    run_service = RunService()
    runs = await run_service.list_runs(project_id=project_id, skip=skip, limit=limit)
    
    return [
        RunResponse(
            id=str(r.id),
            project_id=str(r.project_id),
            mode=r.mode,
            status=r.status,
            stage=r.stage,
            started_at=r.started_at.isoformat() if r.started_at else None,
            finished_at=r.finished_at.isoformat() if r.finished_at else None,
            stats=r.stats.model_dump(),
            error=r.error
        )
        for r in runs
    ]


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    current_user: User = Depends(require_operator)
):
    """Get a specific run"""
    run = await check_run_access(run_id, current_user)
    
    return RunResponse(
        id=str(run.id),
        project_id=str(run.project_id),
        mode=run.mode,
        status=run.status,
        stage=run.stage,
        started_at=run.started_at.isoformat() if run.started_at else None,
        finished_at=run.finished_at.isoformat() if run.finished_at else None,
        stats=run.stats.model_dump(),
        error=run.error
    )


@router.post("/runs/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    current_user: User = Depends(require_operator)
):
    """Cancel a running migration"""
    run = await check_run_access(run_id, current_user)
    
    run_service = RunService()
    cancelled_run = await run_service.cancel_run(run_id)
    if not cancelled_run:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel run"
        )
    
    return {"message": "Run cancelled successfully", "run_id": run_id}


@router.post("/runs/{run_id}/resume")
async def resume_run(
    run_id: str,
    resume_request: ResumeRequest = ResumeRequest(),
    current_user: User = Depends(require_operator)
):
    """Resume a failed or cancelled run"""
    run = await check_run_access(run_id, current_user)
    
    run_service = RunService()
    from_stage = resume_request.from_stage
    resumed_run = await run_service.resume_run(run_id, from_stage)
    
    if not resumed_run:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot resume run (must be FAILED or CANCELED)"
        )
    
    return {"message": "Run resumed successfully", "run_id": run_id}


@router.get("/runs/{run_id}/artifacts", response_model=List[ArtifactResponse])
async def get_run_artifacts(
    run_id: str,
    artifact_type: Optional[str] = Query(None),
    current_user: User = Depends(require_operator)
):
    """Get artifacts for a run"""
    run = await check_run_access(run_id, current_user)
    
    artifact_service = ArtifactService()
    artifacts = await artifact_service.list_artifacts(run_id, artifact_type=artifact_type)
    
    return [
        ArtifactResponse(
            id=str(a.id),
            type=a.type,
            path=a.path,
            size_bytes=a.size_bytes,
            created_at=a.created_at.isoformat(),
            metadata=a.metadata
        )
        for a in artifacts
    ]


@router.get("/runs/{run_id}/plan")
async def get_run_plan(
    run_id: str,
    current_user: User = Depends(require_operator)
):
    """Get migration plan for a run"""
    run = await check_run_access(run_id, current_user)
    
    # TODO: Implement plan retrieval from artifacts
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Plan retrieval not yet implemented"
    )


@router.post("/runs/{run_id}/apply")
async def apply_run(
    run_id: str,
    current_user: User = Depends(require_operator)
):
    """Execute the migration plan (write to GitHub)"""
    run = await check_run_access(run_id, current_user)
    
    # TODO: Implement apply logic (trigger Celery task)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Apply not yet implemented"
    )


@router.post("/runs/{run_id}/verify")
async def verify_run(
    run_id: str,
    current_user: User = Depends(require_operator)
):
    """Verify migration results"""
    run = await check_run_access(run_id, current_user)
    
    # TODO: Implement verify logic (trigger Celery task)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Verify not yet implemented"
    )
