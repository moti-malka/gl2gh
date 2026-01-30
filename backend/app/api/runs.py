"""Migration runs endpoints"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
import json
import logging
import asyncio
from sse_starlette.sse import EventSourceResponse

from app.models import User
from app.services import RunService, ArtifactService, ProjectService
from app.services.connection_service import ConnectionService
from app.api.dependencies import require_operator
from app.api.utils import check_project_access, check_run_access
from app.workers.tasks import run_migration, run_apply, run_verify
from app.utils.sse_manager import sse_manager

logger = logging.getLogger(__name__)

router = APIRouter()


class RunCreate(BaseModel):
    mode: str = "PLAN_ONLY"
    deep: bool = False
    deep_top_n: int = 20
    filters: Optional[Dict[str, Any]] = None


class ResumeRequest(BaseModel):
    from_stage: Optional[str] = None


class ApplyRequest(BaseModel):
    gitlab_project_id: Optional[int] = None
    config: Optional[Dict[str, Any]] = None


class VerifyRequest(BaseModel):
    gitlab_project_id: Optional[int] = None
    config: Optional[Dict[str, Any]] = None


class RunResponse(BaseModel):
    id: str
    project_id: str
    mode: str
    status: str
    stage: Optional[str]
    current_stage: Optional[str] = None
    progress: Dict[str, Any] = {}
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
    project_service = ProjectService()
    connection_service = ConnectionService()
    
    try:
        # Fetch project to get settings (including GitLab/GitHub credentials)
        project = await project_service.get_project(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Fetch GitLab connection and get decrypted token
        gitlab_url = None
        gitlab_token = None
        gitlab_conn = await connection_service.get_connection_by_type(project_id, "gitlab")
        logger.info(f"GitLab connection for project {project_id}: id={gitlab_conn.id if gitlab_conn else None}, base_url={gitlab_conn.base_url if gitlab_conn else None}")
        if gitlab_conn:
            gitlab_url = gitlab_conn.base_url or "https://gitlab.com"
            gitlab_token = await connection_service.get_decrypted_token(str(gitlab_conn.id), project_id)
            logger.info(f"GitLab URL: {gitlab_url}, token retrieved: {gitlab_token is not None}, token starts: {gitlab_token[:10] if gitlab_token else None}...")
        
        # Fetch GitHub connection and get decrypted token
        github_token = None
        github_org = None
        github_conn = await connection_service.get_connection_by_type(project_id, "github")
        logger.info(f"GitHub connection for project {project_id}: id={github_conn.id if github_conn else None}")
        if github_conn:
            github_token = await connection_service.get_decrypted_token(str(github_conn.id), project_id)
            logger.info(f"GitHub token retrieved: {github_token is not None}")
        
        # Get GitHub org from project settings
        settings = project.settings
        if settings.github:
            github_org = settings.github.get("org")
        
        # Build config with all required fields for the agents
        config = {
            # Run options
            "deep": run.deep,
            "deep_top_n": run.deep_top_n,
            "filters": run.filters or {},
            # GitLab settings (from connections)
            "gitlab_url": gitlab_url,
            "gitlab_token": gitlab_token,
            # GitHub settings (from connections)
            "github_token": github_token,
            "github_org": github_org,
            # Budget settings
            "max_api_calls": settings.budgets.get("max_api_calls", 5000) if settings.budgets else 5000,
            "max_per_project_calls": settings.budgets.get("max_per_project_calls", 200) if settings.budgets else 200,
            # Behavior settings  
            "include_archived": settings.behavior.get("include_archived", False) if settings.behavior else False,
            # Output directory
            "output_dir": f"/app/artifacts/runs/{project_id}",
        }
        
        created_run = await run_service.create_run(
            project_id=project_id,
            mode=run.mode,
            config=config
        )
        
        # Dispatch Celery task to start the migration/discovery process
        try:
            run_migration.delay(str(created_run.id), run.mode, config)
        except Exception as e:
            # If task dispatch fails, update run status to indicate the issue
            await run_service.update_run_status(
                run_id=str(created_run.id),
                status="FAILED",
                error={"message": f"Failed to dispatch task: {str(e)}"}
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Run created but failed to start: {str(e)}"
            )
        
        return RunResponse(
            id=str(created_run.id),
            project_id=str(created_run.project_id),
            mode=created_run.mode,
            status=created_run.status,
            stage=created_run.stage,
            current_stage=created_run.current_stage,
            progress=created_run.progress,
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
            current_stage=r.current_stage,
            progress=r.progress,
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
        current_stage=run.current_stage,
        progress=run.progress,
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
    
    # Dispatch Celery task to resume the migration/discovery process
    try:
        run_migration.delay(str(resumed_run.id), resumed_run.mode, resumed_run.config_snapshot)
    except Exception as e:
        # If task dispatch fails, revert run status back to failed
        await run_service.update_run_status(
            run_id=str(resumed_run.id),
            status="FAILED",
            error={"message": f"Failed to dispatch task: {str(e)}"}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume run: {str(e)}"
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
    
    # Get plan artifacts
    artifact_service = ArtifactService()
    plan_artifacts = await artifact_service.list_artifacts(run_id, artifact_type="plan")
    
    if not plan_artifacts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No plan artifacts found for this run"
        )
    
    # Read the plan file content
    # Artifacts are stored relative to artifact_root
    if not run.artifact_root:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run has no artifact root configured"
        )
    
    # Get the first plan artifact (there should typically be one plan per run)
    plan_artifact = plan_artifacts[0]
    plan_file_path = Path(run.artifact_root) / plan_artifact.path
    
    if not plan_file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan file not found"
        )
    
    try:
        # Read and parse the plan file
        with open(plan_file_path, 'r') as f:
            plan_content = json.load(f)
        return plan_content
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse plan file"
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read plan file"
        )


@router.post("/runs/{run_id}/apply")
async def apply_run(
    run_id: str,
    request: Optional[ApplyRequest] = None,
    current_user: User = Depends(require_operator)
):
    """Execute the migration plan (write to GitHub)"""
    run = await check_run_access(run_id, current_user)
    
    # Parse request or use defaults
    if request is None:
        request = ApplyRequest()
    
    # gitlab_project_id is required
    if request.gitlab_project_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="gitlab_project_id is required. Apply must be executed per project."
        )
    
    # Validate that the gitlab_project_id is part of this run
    from app.db import get_database
    from bson import ObjectId
    
    db = await get_database()
    run_project = await db["run_projects"].find_one({
        "run_id": ObjectId(run_id),
        "gitlab_project_id": request.gitlab_project_id
    })
    
    if not run_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"GitLab project {request.gitlab_project_id} not found in this run"
        )
    
    # Prepare config
    config = request.config or {}
    
    # Trigger Celery task for apply
    try:
        task = run_apply.delay(run_id, request.gitlab_project_id, config)
        return {
            "message": "Apply started",
            "run_id": run_id,
            "gitlab_project_id": request.gitlab_project_id,
            "task_id": task.id
        }
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start apply task"
        )


@router.post("/runs/{run_id}/verify")
async def verify_run(
    run_id: str,
    request: Optional[VerifyRequest] = None,
    current_user: User = Depends(require_operator)
):
    """Verify migration results"""
    run = await check_run_access(run_id, current_user)
    
    # Parse request or use defaults
    if request is None:
        request = VerifyRequest()
    
    # gitlab_project_id is required
    if request.gitlab_project_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="gitlab_project_id is required. Verify must be executed per project."
        )
    
    # Validate that the gitlab_project_id is part of this run
    from app.db import get_database
    from bson import ObjectId
    
    db = await get_database()
    run_project = await db["run_projects"].find_one({
        "run_id": ObjectId(run_id),
        "gitlab_project_id": request.gitlab_project_id
    })
    
    if not run_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"GitLab project {request.gitlab_project_id} not found in this run"
        )
    
    # Prepare config
    config = request.config or {}
    
    # Trigger Celery task for verify
    try:
        task = run_verify.delay(run_id, request.gitlab_project_id, config)
        return {
            "message": "Verification started",
            "run_id": run_id,
            "gitlab_project_id": request.gitlab_project_id,
            "task_id": task.id
        }
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start verify task"
        )


@router.get("/runs/{run_id}/progress")
async def get_run_progress(
    run_id: str,
    current_user: User = Depends(require_operator)
):
    """
    Get current run progress (REST polling fallback)
    
    This endpoint provides a REST-based fallback for clients that cannot
    use WebSocket or SSE connections. Clients can poll this endpoint to
    get the latest run progress.
    """
    run = await check_run_access(run_id, current_user)
    
    return {
        "run_id": str(run.id),
        "status": run.status,
        "stage": run.stage,
        "current_stage": run.current_stage,
        "progress": run.progress,
        "stats": run.stats.model_dump(),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "error": run.error
    }


@router.get("/runs/{run_id}/stream")
async def run_events_stream(
    run_id: str,
    current_user: User = Depends(require_operator)
):
    """
    SSE stream for run progress (WebSocket alternative)
    
    This endpoint provides Server-Sent Events as an alternative to WebSocket
    for real-time updates. It's more reliable on unstable networks and
    doesn't require special protocol support.
    """
    # Check access first
    await check_run_access(run_id, current_user)
    
    async def event_generator():
        """Generate SSE events for this run"""
        # Subscribe to updates for this run
        queue = await sse_manager.subscribe(run_id)
        
        try:
            # Send initial connection message
            run_service = RunService()
            run = await run_service.get_run(run_id)
            if run:
                initial_data = {
                    "run_id": str(run.id),
                    "status": run.status,
                    "stage": run.stage,
                    "current_stage": run.current_stage,
                    "progress": run.progress,
                    "stats": run.stats.model_dump(),
                    "started_at": run.started_at.isoformat() if run.started_at else None,
                    "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                }
                yield {
                    "event": "connected",
                    "data": json.dumps(initial_data)
                }
            
            # Stream updates from the queue
            while True:
                try:
                    # Wait for updates with timeout to send keepalive
                    update = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield {
                        "event": "run_update",
                        "data": json.dumps(update)
                    }
                except asyncio.TimeoutError:
                    # Send keepalive comment to keep connection alive
                    yield {
                        "event": "keepalive",
                        "data": json.dumps({"timestamp": datetime.utcnow().isoformat()})
                    }
        except asyncio.CancelledError:
            # Client disconnected
            logger.info(f"SSE client disconnected from run {run_id}")
        finally:
            # Clean up subscription
            await sse_manager.unsubscribe(run_id, queue)
    
    return EventSourceResponse(event_generator())
