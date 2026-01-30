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
from app.services.report_service import MigrationReportGenerator
from app.api.dependencies import require_operator
from app.api.utils import check_project_access, check_run_access
from app.workers.tasks import run_migration, run_apply, run_verify
from app.utils.sse_manager import sse_manager

logger = logging.getLogger(__name__)

router = APIRouter()


class RunCreate(BaseModel):
    mode: str = "PLAN_ONLY"  # PLAN_ONLY, DRY_RUN, EXECUTE
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


class ProjectSelection(BaseModel):
    gitlab_project_id: int
    path_with_namespace: str
    target_repo_name: str
    selected: bool


class SelectionRequest(BaseModel):
    selections: List[ProjectSelection]
class BatchMigrationRequest(BaseModel):
    """Request model for batch migration of multiple projects"""
    project_ids: List[int]  # List of GitLab project IDs to migrate
    mode: str = "PLAN_ONLY"
    parallel_limit: int = 5  # Maximum concurrent migrations
    resume_from: Optional[str] = None


class BatchMigrationResponse(BaseModel):
    """Response model for batch migration"""
    batch_id: str  # Identifier for tracking this batch
    total_projects: int
    parallel_limit: int
    status: str
    message: str


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
        
        # Get scope from gitlab settings
        scope_type = settings.gitlab.get("scope_type") if settings.gitlab else None
        scope_id = settings.gitlab.get("scope_id") if settings.gitlab else None
        scope_path = settings.gitlab.get("scope_path") if settings.gitlab else None
        
        # Build config with all required fields for the agents
        config = {
            # Run options
            "deep": run.deep,
            "deep_top_n": run.deep_top_n,
            "filters": run.filters or {},
            # GitLab settings (from connections)
            "gitlab_url": gitlab_url,
            "gitlab_token": gitlab_token,
            # Scope settings (what to migrate)
            "scope_type": scope_type,  # 'project' or 'group'
            "scope_id": scope_id,       # GitLab project/group ID
            "scope_path": scope_path,   # Full path like 'org/repo' or 'org/group'
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


@router.get("/runs/{run_id}/stream")
async def stream_run_events(
    run_id: str,
    token: str = Query(..., description="Authentication token")
):
    """
    Stream real-time run updates via Server-Sent Events (SSE)
    
    This endpoint provides a fallback for WebSocket connections.
    Authentication is done via query parameter since SSE doesn't support headers.
    Polls the database for updates since worker runs in a separate process.
    """
    from app.utils.auth import verify_token
    from app.services import RunService, EventService
    
    # Validate token from query parameter
    try:
        payload = verify_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid token")
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"SSE auth failed: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")
    
    # Verify run exists and user has access
    run_service = RunService()
    run = await run_service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    async def event_generator():
        """Generate SSE events for this run by polling the database"""
        event_service = EventService()
        last_event_count = 0
        last_status = None
        last_stage = None
        
        try:
            # Send initial state
            current_run = await run_service.get_run(run_id)
            if current_run:
                last_status = current_run.status
                last_stage = current_run.stage
                yield {
                    "event": "state",
                    "data": json.dumps({
                        "status": current_run.status,
                        "stage": current_run.stage,
                        "current_stage": current_run.current_stage,
                        "progress": current_run.progress,
                        "stats": current_run.stats.model_dump() if current_run.stats else {}
                    })
                }
            
            # Poll for updates
            while True:
                await asyncio.sleep(2)  # Poll every 2 seconds
                
                # Get current run state
                current_run = await run_service.get_run(run_id)
                if not current_run:
                    break
                
                # Check if status or stage changed
                if current_run.status != last_status or current_run.stage != last_stage:
                    last_status = current_run.status
                    last_stage = current_run.stage
                    
                    yield {
                        "event": "update",
                        "data": json.dumps({
                            "status": current_run.status,
                            "stage": current_run.stage,
                            "current_stage": current_run.current_stage,
                            "progress": current_run.progress,
                            "stats": current_run.stats.model_dump() if current_run.stats else {}
                        })
                    }
                
                # Get new events
                events = await event_service.get_events(run_id, skip=last_event_count, limit=50)
                if events:
                    for event in events:
                        yield {
                            "event": "log",
                            "data": json.dumps({
                                "level": event.level,
                                "message": event.message,
                                "agent": event.agent,
                                "timestamp": event.timestamp.isoformat() if event.timestamp else None
                            })
                        }
                    last_event_count += len(events)
                
                # Check if run is completed
                if current_run.status in ["COMPLETED", "FAILED", "CANCELLED", "success"]:
                    yield {
                        "event": "complete",
                        "data": json.dumps({"status": current_run.status})
                    }
                    break
                        
        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled for run {run_id}")
    
    return EventSourceResponse(event_generator())


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


@router.get("/runs/{run_id}/checkpoint")
async def get_checkpoint(
    run_id: str,
    current_user: User = Depends(require_operator)
):
    """Get checkpoint status for a run"""
    run = await check_run_access(run_id, current_user)
    
    # Check if run has artifact root
    if not run.artifact_root:
        return {
            "has_checkpoint": False,
            "components": {},
            "resumable": False,
            "resume_from": None
        }
    
    # Look for checkpoint file in export directory
    # Validate artifact_root to prevent path traversal
    try:
        artifact_root = Path(run.artifact_root).resolve()
        checkpoint_file = (artifact_root / "export" / ".export_checkpoint.json").resolve()
        
        # Ensure checkpoint file is within artifact root
        if not str(checkpoint_file).startswith(str(artifact_root)):
            logger.warning(f"Potential path traversal attempt for run {run_id}")
            return {
                "has_checkpoint": False,
                "components": {},
                "resumable": False,
                "resume_from": None
            }
    except Exception as e:
        logger.error(f"Path validation error: {e}")
        return {
            "has_checkpoint": False,
            "components": {},
            "resumable": False,
            "resume_from": None
        }
    
    if not checkpoint_file.exists():
        return {
            "has_checkpoint": False,
            "components": {},
            "resumable": False,
            "resume_from": None
        }
    
    try:
        # Read checkpoint data
        with open(checkpoint_file, 'r') as f:
            checkpoint_data = json.load(f)
        
        # Determine if resumable and from where
        components = checkpoint_data.get("components", {})
        resumable = False
        resume_from = None
        
        # Find first non-completed component
        for component_name, component_data in components.items():
            if component_data.get("status") in ["in_progress", "failed"]:
                resumable = True
                if resume_from is None:
                    resume_from = component_name
        
        return {
            "has_checkpoint": True,
            "components": components,
            "resumable": resumable,
            "resume_from": resume_from,
            "started_at": checkpoint_data.get("started_at"),
            "updated_at": checkpoint_data.get("updated_at"),
            "errors": checkpoint_data.get("errors", [])
        }
        
    except Exception as e:
        logger.error(f"Failed to read checkpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read checkpoint: {str(e)}"
        )


@router.post("/runs/{run_id}/resume")
async def resume_run(
    run_id: str,
    resume_request: ResumeRequest = ResumeRequest(),
    current_user: User = Depends(require_operator)
):
    """Resume a failed or cancelled run from checkpoint"""
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
    # Set resume flag in config
    config = resumed_run.config_snapshot.copy()
    config["resume"] = True
    
    try:
        run_migration.delay(str(resumed_run.id), resumed_run.mode, config)
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


@router.delete("/runs/{run_id}/checkpoint")
async def clear_checkpoint(
    run_id: str,
    current_user: User = Depends(require_operator)
):
    """Clear checkpoint for a run to start fresh"""
    run = await check_run_access(run_id, current_user)
    
    # Only allow clearing checkpoint for failed or canceled runs
    if run.status not in ["FAILED", "CANCELED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot clear checkpoint for run with status {run.status}. Only FAILED or CANCELED runs can have checkpoints cleared."
        )
    
    # Check if run has artifact root
    if not run.artifact_root:
        return {"message": "No checkpoint to clear"}
    
    # Look for checkpoint file in export directory
    # Validate artifact_root to prevent path traversal
    try:
        artifact_root = Path(run.artifact_root).resolve()
        checkpoint_file = (artifact_root / "export" / ".export_checkpoint.json").resolve()
        
        # Ensure checkpoint file is within artifact root
        if not str(checkpoint_file).startswith(str(artifact_root)):
            logger.warning(f"Potential path traversal attempt for run {run_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid checkpoint path"
            )
    except Exception as e:
        logger.error(f"Path validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid artifact path"
        )
    
    if not checkpoint_file.exists():
        return {"message": "No checkpoint to clear"}
    
    try:
        # Delete checkpoint file
        checkpoint_file.unlink()
        logger.info(f"Cleared checkpoint for run {run_id}")
        return {"message": "Checkpoint cleared successfully"}
        
    except Exception as e:
        logger.error(f"Failed to clear checkpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear checkpoint: {str(e)}"
        )


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


@router.get("/runs/{run_id}/summary")
async def get_run_summary(
    run_id: str,
    current_user: User = Depends(require_operator)
):
    """
    Get a human-readable summary of what the run discovered and planned.
    This provides actionable information for the user.
    """
    import json
    from pathlib import Path
    
    run = await check_run_access(run_id, current_user)
    
    summary = {
        "run_id": run_id,
        "status": run.status,
        "mode": run.mode,
        "discovery": None,
        "plan": None,
        "next_steps": [],
        "artifacts_available": []
    }
    
    # Get project info
    project_service = ProjectService()
    project = await project_service.get_project(str(run.project_id))
    
    # Artifacts are stored by project_id, not run_id
    artifact_root = Path(f"/app/artifacts/runs/{run.project_id}")
    logger.info(f"Looking for artifacts in: {artifact_root}")
    
    # Try to read discovery results (inventory.json) - directly in artifact_root
    inventory_path = artifact_root / "inventory.json"
    
    if inventory_path.exists():
        try:
            with open(inventory_path) as f:
                inventory = json.load(f)
            
            # Extract summary from inventory
            projects = inventory.get("projects", [])
            summary["discovery"] = {
                "total_projects": len(projects),
                "projects": [
                    {
                        "name": p.get("name"),
                        "path": p.get("path_with_namespace"),
                        "visibility": p.get("visibility"),
                        "components": list(p.get("components", {}).keys()) if isinstance(p.get("components"), dict) else []
                    }
                    for p in projects[:10]  # Limit to first 10
                ],
                "has_more": len(projects) > 10
            }
            summary["artifacts_available"].append("inventory")
        except Exception as e:
            logger.warning(f"Could not read inventory: {e}")
    else:
        logger.info(f"No inventory found at {inventory_path}")
    
    # Try to read plan.json - directly in artifact_root
    plan_path = artifact_root / "plan.json"
    if plan_path.exists():
        try:
            with open(plan_path) as f:
                plan = json.load(f)
            
            actions = plan.get("actions", [])
            summary["plan"] = {
                "total_actions": len(actions),
                "actions_by_type": {},
                "preview": actions[:5]  # First 5 actions
            }
            
            # Count by type
            for action in actions:
                action_type = action.get("type", "unknown")
                summary["plan"]["actions_by_type"][action_type] = \
                    summary["plan"]["actions_by_type"].get(action_type, 0) + 1
            
            summary["artifacts_available"].append("plan")
        except Exception as e:
            logger.warning(f"Could not read plan: {e}")
    
    # Try to read conversion_gaps.json - directly in artifact_root
    gaps_path = artifact_root / "conversion_gaps.json"
    if gaps_path.exists():
        try:
            with open(gaps_path) as f:
                gaps = json.load(f)
            summary["gaps"] = {
                "total": len(gaps.get("gaps", [])),
                "by_severity": gaps.get("by_severity", {}),
                "preview": gaps.get("gaps", [])[:3]
            }
            summary["artifacts_available"].append("gaps")
        except Exception as e:
            logger.warning(f"Could not read gaps: {e}")
    
    # Determine next steps based on mode and status
    if run.status == "COMPLETED":
        if run.mode == "DISCOVER_ONLY":
            summary["next_steps"] = [
                {"action": "review_discovery", "label": "Review Discovered Projects", "description": "Review the discovered projects and their components"},
                {"action": "create_plan", "label": "Create Migration Plan", "description": "Start a new run in PLAN_ONLY mode to create migration plan"}
            ]
        elif run.mode == "PLAN_ONLY":
            summary["next_steps"] = [
                {"action": "review_plan", "label": "Review Migration Plan", "description": "Review the generated migration plan and actions"},
                {"action": "download_plan", "label": "Download Plan", "description": "Download the plan.json file for review"},
                {"action": "apply", "label": "Apply Migration", "description": "Execute the migration plan on GitHub", "primary": True}
            ]
        elif run.mode in ["APPLY", "FULL"]:
            summary["next_steps"] = [
                {"action": "verify", "label": "Verify Migration", "description": "Run verification to check migration results"},
                {"action": "view_github", "label": "View on GitHub", "description": "Open GitHub to see migrated repositories"}
            ]
    elif run.status == "FAILED":
        summary["next_steps"] = [
            {"action": "view_errors", "label": "View Errors", "description": "Check the error details below"},
            {"action": "resume", "label": "Resume from Checkpoint", "description": "Resume the run from where it failed"}
        ]
    
    return summary


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


@router.get("/runs/{run_id}/discovery-results")
async def get_discovery_results(
    run_id: str,
    current_user: User = Depends(require_operator)
):
    """Get discovery results for a run"""
    run = await check_run_access(run_id, current_user)
    
    # Check if discovery has completed
    # Discovery is complete if stage is past DISCOVER or if run is completed
    discovery_complete = (
        run.stage in ["EXPORT", "TRANSFORM", "PLAN", "APPLY", "VERIFY", "DONE"] or
        run.status in ["COMPLETED", "success"] or
        (run.status == "COMPLETED" and run.mode == "DISCOVER_ONLY")
    )
    
    if not discovery_complete:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discovery has not completed yet"
        )
    
    # Get discovery artifacts (inventory.json)
    artifact_service = ArtifactService()
    discovery_artifacts = await artifact_service.list_artifacts(run_id, artifact_type="inventory")
    
    if not discovery_artifacts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No discovery artifacts found for this run"
        )
    
    # Read the inventory file content
@router.post("/runs/{run_id}/rollback")
async def rollback_run(
    run_id: str,
    current_user: User = Depends(require_operator)
):
    """Rollback all actions from a failed or partially completed migration"""
    run = await check_run_access(run_id, current_user)
    
    # Validate that rollback is appropriate for this run
    if run.status not in ["FAILED", "COMPLETED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot rollback run with status {run.status}. Only FAILED or COMPLETED runs can be rolled back."
        )
    
    # Check for executed_actions.json artifact
    artifact_service = ArtifactService()
    
    if not run.artifact_root:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run has no artifact root configured"
        )
    
    # Get the first inventory artifact
    inventory_artifact = discovery_artifacts[0]
    inventory_file_path = Path(run.artifact_root) / inventory_artifact.path
    
    if not inventory_file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory file not found"
        )
    
    try:
        # Read and parse the inventory file
        with open(inventory_file_path, 'r') as f:
            inventory_content = json.load(f)
        
        # Extract projects with enhanced metrics
        projects = inventory_content.get("projects", [])
        enhanced_projects = []
        
        for project in projects:
            components = project.get("components", {})
            
            # Calculate metrics
            repo = components.get("repository", {})
            commits_count = repo.get("branches_count", 0)  # Approximate
            
            issues = components.get("issues", {})
            issues_count = issues.get("opened_count", 0)
            
            mrs = components.get("merge_requests", {})
            mrs_count = mrs.get("opened_count", 0)
            
            ci_cd = components.get("ci_cd", {})
            has_ci = ci_cd.get("has_gitlab_ci", False)
            
            # Calculate readiness score (0-100)
            # Simple heuristic: projects with fewer components are "easier"
            score = 100
            if has_ci:
                score -= 15  # CI requires conversion
            if issues_count > 0:
                score -= min(10, issues_count)  # More issues = more complex
            if mrs_count > 0:
                score -= min(10, mrs_count * 2)  # More MRs = more complex
            score = max(0, score)
            
            enhanced_projects.append({
                "id": project.get("id"),
                "name": project.get("name"),
                "path_with_namespace": project.get("path_with_namespace"),
                "description": project.get("description"),
                "web_url": project.get("web_url"),
                "metrics": {
                    "commits": commits_count,
                    "issues": issues_count,
                    "merge_requests": mrs_count,
                    "has_ci": has_ci,
                },
                "readiness_score": score,
                "components": components
            })
        
        return {
            "version": inventory_content.get("version"),
            "generated_at": inventory_content.get("generated_at"),
            "projects_count": len(enhanced_projects),
            "projects": enhanced_projects
        }
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse inventory file"
        )
    except Exception as e:
        logger.error(f"Failed to read inventory file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read inventory file"
        )


@router.post("/runs/{run_id}/selection")
async def save_project_selection(
    run_id: str,
    request: SelectionRequest,
    current_user: User = Depends(require_operator)
):
    """Save user's project selection for migration"""
    run = await check_run_access(run_id, current_user)
    
    from app.db import get_database
    from bson import ObjectId
    import re
    
    # Validate target repo names format (owner/repo)
    github_repo_pattern = re.compile(r'^[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+$')
    
    for sel in request.selections:
        if sel.selected and not github_repo_pattern.match(sel.target_repo_name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid target repo name format: {sel.target_repo_name}. Must be owner/repo-name"
            )
    
    # Validate that all project IDs exist in the discovery results
    try:
        artifact_service = ArtifactService()
        discovery_artifacts = await artifact_service.list_artifacts(run_id, artifact_type="inventory")
        
        if discovery_artifacts and run.artifact_root:
            inventory_artifact = discovery_artifacts[0]
            inventory_file_path = Path(run.artifact_root) / inventory_artifact.path
            
            if inventory_file_path.exists():
                with open(inventory_file_path, 'r') as f:
                    inventory_content = json.load(f)
                    discovered_project_ids = {p.get("id") for p in inventory_content.get("projects", [])}
                    
                    # Validate all selected project IDs exist in discovery
                    for sel in request.selections:
                        if sel.selected and sel.gitlab_project_id not in discovered_project_ids:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Project ID {sel.gitlab_project_id} not found in discovery results"
                            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Could not validate project IDs against discovery results: {str(e)}")
        # Continue anyway - validation is best-effort
    
    db = await get_database()
    
    # Store selection in run's config
    selection_data = {
        "selected_projects": [
            {
                "gitlab_project_id": sel.gitlab_project_id,
                "path_with_namespace": sel.path_with_namespace,
                "target_repo_name": sel.target_repo_name,
                "selected": sel.selected
            }
            for sel in request.selections
        ],
        "selected_at": datetime.utcnow().isoformat()
    }
    
    # Update run with selection data
    await db["migration_runs"].update_one(
        {"_id": ObjectId(run_id)},
        {
            "$set": {
                "config_snapshot.project_selection": selection_data,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return {
        "message": "Project selection saved",
        "run_id": run_id,
        "selected_count": sum(1 for sel in request.selections if sel.selected)
    }
    # Look for executed_actions.json file
    executed_actions_path = Path(run.artifact_root) / "apply" / "executed_actions.json"
    
    if not executed_actions_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No executed actions found for this run. The run may not have reached the apply stage."
        )
    
    try:
        # Initialize ApplyAgent and GitHub client
        from app.agents.apply_agent import ApplyAgent
        from app.services.connection_service import ConnectionService
        from github import Github
        
        connection_service = ConnectionService()
        project_service = ProjectService()
        
        # Get project to fetch GitHub token
        project = await project_service.get_project(str(run.project_id))
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Fetch GitHub connection and get decrypted token
        github_conn = await connection_service.get_connection_by_type(str(run.project_id), "github")
        if not github_conn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="GitHub connection not found for this project"
            )
        
        github_token = await connection_service.get_decrypted_token(str(github_conn.id), str(run.project_id))
        if not github_token:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve GitHub token"
            )
        
        # Initialize GitHub client and apply agent
        github_client = Github(github_token)
        apply_agent = ApplyAgent()
        apply_agent.github_client = github_client
        apply_agent.execution_context = {
            "github_token": github_token,
            "output_dir": str(run.artifact_root)
        }
        
        # Perform rollback
        rollback_result = await apply_agent.rollback_migration(str(executed_actions_path))
        
        # Save rollback report
        rollback_report_path = Path(run.artifact_root) / "apply" / "rollback_report.json"
        rollback_report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(rollback_report_path, 'w') as f:
            json.dump({
                **rollback_result,
                "timestamp": datetime.utcnow().isoformat(),
                "run_id": run_id
            }, f, indent=2)
        
        return {
            "message": "Rollback completed",
            "run_id": run_id,
            **rollback_result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rollback failed for run {run_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rollback failed: {str(e)}"
        )
