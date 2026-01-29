"""Common API utilities"""

from fastapi import HTTPException, status
from app.models import User
from app.services import ProjectService, RunService


async def check_project_access(project_id: str, current_user: User):
    """
    Check if user has access to project
    
    Args:
        project_id: Project ID
        current_user: Current authenticated user
        
    Returns:
        Project if access granted
        
    Raises:
        HTTPException: If project not found or access denied
    """
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
    
    return project


async def check_run_access(run_id: str, current_user: User):
    """
    Check if user has access to run
    
    Args:
        run_id: Run ID
        current_user: Current authenticated user
        
    Returns:
        Run if access granted
        
    Raises:
        HTTPException: If run not found or access denied
    """
    run_service = RunService()
    run = await run_service.get_run(run_id)
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found"
        )
    
    # Check project access
    await check_project_access(str(run.project_id), current_user)
    
    return run
