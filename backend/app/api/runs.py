"""Migration runs endpoints"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

router = APIRouter()


class RunCreate(BaseModel):
    mode: str = "PLAN_ONLY"
    deep: bool = False
    deep_top_n: int = 20
    filters: Optional[Dict[str, Any]] = None


class RunResponse(BaseModel):
    id: str
    project_id: str
    mode: str
    status: str
    stage: Optional[str]
    started_at: Optional[str]
    finished_at: Optional[str]
    stats: Dict[str, int]


@router.post("/projects/{project_id}/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(project_id: str, run: RunCreate):
    """Create and start a new migration run"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Run creation not yet implemented"
    )


@router.get("/projects/{project_id}/runs", response_model=List[RunResponse])
async def list_project_runs(project_id: str):
    """List all runs for a project"""
    return []


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(run_id: str):
    """Get a specific run"""
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Run {run_id} not found"
    )


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str):
    """Cancel a running migration"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Run cancellation not yet implemented"
    )


@router.post("/runs/{run_id}/resume")
async def resume_run(run_id: str):
    """Resume a failed or cancelled run"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Run resume not yet implemented"
    )


@router.get("/runs/{run_id}/artifacts")
async def get_run_artifacts(run_id: str):
    """Get artifacts for a run"""
    return {"artifacts": []}


@router.get("/runs/{run_id}/plan")
async def get_run_plan(run_id: str):
    """Get migration plan for a run"""
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Plan not found"
    )


@router.post("/runs/{run_id}/apply")
async def apply_run(run_id: str):
    """Execute the migration plan (write to GitHub)"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Apply not yet implemented"
    )


@router.post("/runs/{run_id}/verify")
async def verify_run(run_id: str):
    """Verify migration results"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Verify not yet implemented"
    )
