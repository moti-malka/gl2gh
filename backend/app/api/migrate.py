"""Quick migration endpoints"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any
import re
import logging

from app.models import User
from app.services import RunService
from app.api.dependencies import require_operator
from app.workers.tasks import run_migration

logger = logging.getLogger(__name__)

router = APIRouter()


class MigrationOptions(BaseModel):
    """Migration options for quick migrate"""
    include_ci: bool = True
    include_issues: bool = True
    include_wiki: bool = False
    include_releases: bool = False


class QuickMigrateRequest(BaseModel):
    """Request model for quick migration"""
    gitlab_url: str = Field(..., description="GitLab instance URL (e.g., https://gitlab.com)")
    gitlab_project_path: str = Field(..., description="GitLab project path (e.g., moti.malka25/demo-project)")
    gitlab_token: str = Field(..., description="GitLab Personal Access Token")
    github_org: str = Field(..., description="GitHub organization or user name")
    github_repo_name: str = Field(..., description="GitHub repository name")
    github_token: str = Field(..., description="GitHub Personal Access Token")
    options: Optional[MigrationOptions] = MigrationOptions()
    
    @validator('gitlab_url')
    def validate_gitlab_url(cls, v):
        """Validate GitLab URL format"""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('GitLab URL must start with http:// or https://')
        # Remove trailing slash
        return v.rstrip('/')
    
    @validator('gitlab_project_path')
    def validate_gitlab_project_path(cls, v):
        """Validate GitLab project path format"""
        # Should be in format: username/project or group/subgroup/project
        if not re.match(r'^[\w\-\.]+(/[\w\-\.]+)+$', v):
            raise ValueError('Invalid GitLab project path format. Expected: username/project or group/subgroup/project')
        return v
    
    @validator('github_org', 'github_repo_name')
    def validate_github_names(cls, v):
        """Validate GitHub org and repo names"""
        # GitHub names can only contain alphanumeric, hyphens, and underscores
        if not re.match(r'^[\w\-]+$', v):
            raise ValueError('Invalid GitHub name format. Only alphanumeric, hyphens, and underscores allowed')
        return v


class QuickMigrateResponse(BaseModel):
    """Response model for quick migration"""
    run_id: str
    status: str
    dashboard_url: str
    message: str


@router.post("/migrate/quick", response_model=QuickMigrateResponse, status_code=status.HTTP_201_CREATED)
async def quick_migrate(
    request: QuickMigrateRequest,
    current_user: User = Depends(require_operator)
):
    """
    Quick migration endpoint for single GitLab project.
    
    This endpoint allows users to quickly migrate a single GitLab project
    by providing the project URL and credentials directly, without needing
    to create a project and configure connections first.
    
    The migration will:
    1. Skip the discovery stage (no need to scan all projects)
    2. Directly use the specified GitLab project info
    3. Proceed with export, transform, and plan stages
    
    Note: This creates a run in "PLAN_ONLY" mode for safety - the actual
    migration execution (apply) can be triggered separately after reviewing
    the plan.
    """
    logger.info(f"Quick migrate request received for project in {request.gitlab_url}")
    
    run_service = RunService()
    
    try:
        # Build config for single-project migration
        # Note: Tokens are stored in config and should be handled securely
        # throughout the migration pipeline
        config = {
            # Mark as single project mode for orchestrator
            "single_project": True,
            "single_project_path": request.gitlab_project_path,
            
            # GitLab settings
            "gitlab_url": request.gitlab_url,
            "gitlab_token": request.gitlab_token,
            
            # GitHub settings
            "github_token": request.github_token,
            "github_org": request.github_org,
            "github_repo_name": request.github_repo_name,
            
            # Migration options
            "include_ci": request.options.include_ci,
            "include_issues": request.options.include_issues,
            "include_wiki": request.options.include_wiki,
            "include_releases": request.options.include_releases,
            
            # Disable deep analysis for quick migration
            "deep": False,
            "filters": {},
            
            # Budget settings (use reasonable defaults)
            "max_api_calls": 5000,
            "max_per_project_calls": 200,
            
            # Output directory (temporary for quick migrations)
            "output_dir": f"/app/artifacts/quick-runs/{current_user.username}",
        }
        
        # Create a run with a unique project_id for quick migrations
        # Format: quick-migration-{username}-{timestamp}
        import time
        project_id = f"quick-migration-{current_user.username}-{int(time.time())}"
        
        # Quick migrations use SINGLE_PROJECT mode
        created_run = await run_service.create_run(
            project_id=project_id,
            mode="SINGLE_PROJECT",
            config=config
        )
        
        # Dispatch Celery task to start the migration process
        try:
            run_migration.delay(str(created_run.id), "SINGLE_PROJECT", config)
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
        
        dashboard_url = f"/runs/{created_run.id}"
        
        return QuickMigrateResponse(
            run_id=str(created_run.id),
            status="started",
            dashboard_url=dashboard_url,
            message=f"Quick migration started for {request.gitlab_project_path}"
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid input: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to start quick migration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start quick migration: {str(e)}"
        )
