"""Tests for RunService"""

import pytest


@pytest.mark.asyncio
async def test_create_run(run_service, test_project):
    """Test run creation"""
    run = await run_service.create_run(
        project_id=str(test_project.id),
        mode="PLAN_ONLY",
        config={"deep": True}
    )
    
    assert run.mode == "PLAN_ONLY"
    assert run.status == "CREATED"
    assert str(run.project_id) == str(test_project.id)
    assert run.config_snapshot["deep"] is True
    assert run.id is not None


@pytest.mark.asyncio
async def test_get_run(run_service, test_project):
    """Test getting run by ID"""
    created_run = await run_service.create_run(
        project_id=str(test_project.id),
        mode="FULL"
    )
    
    run = await run_service.get_run(str(created_run.id))
    assert run is not None
    assert str(run.id) == str(created_run.id)
    assert run.mode == "FULL"


@pytest.mark.asyncio
async def test_list_runs(run_service, test_project):
    """Test listing runs"""
    # Create multiple runs
    await run_service.create_run(str(test_project.id), "PLAN_ONLY")
    await run_service.create_run(str(test_project.id), "FULL")
    
    runs = await run_service.list_runs(project_id=str(test_project.id))
    assert len(runs) >= 2


@pytest.mark.asyncio
async def test_update_run_status(run_service, test_project):
    """Test updating run status"""
    run = await run_service.create_run(str(test_project.id), "PLAN_ONLY")
    
    updated = await run_service.update_run_status(
        str(run.id),
        "RUNNING",
        stage="DISCOVER"
    )
    
    assert updated is not None
    assert updated.status == "RUNNING"
    assert updated.stage == "DISCOVER"
    assert updated.started_at is not None


@pytest.mark.asyncio
async def test_cancel_run(run_service, test_project):
    """Test cancelling a run"""
    run = await run_service.create_run(str(test_project.id), "FULL")
    await run_service.update_run_status(str(run.id), "RUNNING")
    
    cancelled = await run_service.cancel_run(str(run.id))
    assert cancelled is not None
    assert cancelled.status == "CANCELED"


@pytest.mark.asyncio
async def test_resume_run(run_service, test_project):
    """Test resuming a run"""
    run = await run_service.create_run(str(test_project.id), "FULL")
    await run_service.update_run_status(str(run.id), "FAILED", stage="EXPORT")
    
    resumed = await run_service.resume_run(str(run.id), from_stage="EXPORT")
    assert resumed is not None
    assert resumed.status == "QUEUED"
    assert resumed.error is None


@pytest.mark.asyncio
async def test_increment_run_stats(run_service, test_project):
    """Test incrementing run statistics"""
    run = await run_service.create_run(str(test_project.id), "FULL")
    
    success = await run_service.increment_run_stats(str(run.id), "projects", 5)
    assert success is True
    
    updated_run = await run_service.get_run(str(run.id))
    assert updated_run.stats.projects == 5
