"""User mapping endpoints for GitLab to GitHub user mappings"""

from fastapi import APIRouter, HTTPException, status, Depends, Query, Path
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from app.models import User
from app.services import UserMappingService
from app.api.dependencies import get_current_active_user
from bson import ObjectId

router = APIRouter()


class UserMappingCreate(BaseModel):
    """Request body for creating/updating a user mapping"""
    gitlab_username: str = Field(..., description="GitLab username")
    gitlab_email: Optional[str] = Field(None, description="GitLab email")
    github_username: Optional[str] = Field(None, description="GitHub username")
    confidence: Optional[float] = Field(1.0, ge=0.0, le=1.0, description="Confidence score")
    match_method: Optional[str] = Field("manual", description="Match method")
    project_id: Optional[str] = Field(None, description="Optional project ID for project-level mapping")


class UserMappingUpdate(BaseModel):
    """Request body for updating a user mapping"""
    github_username: Optional[str] = Field(None, description="GitHub username")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score")


class UserMappingResponse(BaseModel):
    """Response model for user mapping"""
    id: str
    run_id: str
    project_id: Optional[str] = None
    gitlab_username: str
    gitlab_email: Optional[str]
    github_username: Optional[str]
    confidence: float
    match_method: Optional[str]
    is_manual: bool
    created_at: str
    updated_at: str


@router.get("/{run_id}/user-mappings", response_model=List[UserMappingResponse])
async def list_user_mappings(
    run_id: str = Path(..., description="Run ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_active_user)
):
    """List all user mappings for a run"""
    service = UserMappingService()
    
    try:
        mappings = await service.get_mappings(run_id, skip=skip, limit=limit)
        
        return [
            UserMappingResponse(
                id=str(m.id),
                run_id=str(m.run_id),
                project_id=str(m.project_id) if m.project_id else None,
                gitlab_username=m.gitlab_username,
                gitlab_email=m.gitlab_email,
                github_username=m.github_username,
                confidence=m.confidence,
                match_method=m.match_method,
                is_manual=m.is_manual,
                created_at=m.created_at.isoformat(),
                updated_at=m.updated_at.isoformat()
            )
            for m in mappings
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list user mappings: {str(e)}"
        )


@router.get("/{run_id}/user-mappings/unmapped", response_model=List[UserMappingResponse])
async def list_unmapped_users(
    run_id: str = Path(..., description="Run ID"),
    current_user: User = Depends(get_current_active_user)
):
    """List all unmapped GitLab users for a run"""
    service = UserMappingService()
    
    try:
        mappings = await service.get_unmapped_users(run_id)
        
        return [
            UserMappingResponse(
                id=str(m.id),
                run_id=str(m.run_id),
                project_id=str(m.project_id) if m.project_id else None,
                gitlab_username=m.gitlab_username,
                gitlab_email=m.gitlab_email,
                github_username=m.github_username,
                confidence=m.confidence,
                match_method=m.match_method,
                is_manual=m.is_manual,
                created_at=m.created_at.isoformat(),
                updated_at=m.updated_at.isoformat()
            )
            for m in mappings
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list unmapped users: {str(e)}"
        )


@router.get("/{run_id}/user-mappings/stats")
async def get_mapping_stats(
    run_id: str = Path(..., description="Run ID"),
    current_user: User = Depends(get_current_active_user)
):
    """Get statistics about user mappings for a run"""
    service = UserMappingService()
    
    try:
        total = await service.count_mappings(run_id, mapped_only=False)
        mapped = await service.count_mappings(run_id, mapped_only=True)
        unmapped = total - mapped
        
        return {
            "total": total,
            "mapped": mapped,
            "unmapped": unmapped,
            "coverage_percent": round((mapped / total * 100) if total > 0 else 0, 2)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get mapping stats: {str(e)}"
        )


@router.post("/{run_id}/user-mappings", response_model=UserMappingResponse, status_code=status.HTTP_201_CREATED)
async def create_user_mapping(
    run_id: str = Path(..., description="Run ID"),
    mapping: UserMappingCreate = ...,
    current_user: User = Depends(get_current_active_user)
):
    """Create or update a user mapping (manual mapping)"""
    service = UserMappingService()
    
    try:
        created_mapping = await service.store_mapping(
            run_id=run_id,
            gitlab_username=mapping.gitlab_username,
            github_username=mapping.github_username,
            gitlab_email=mapping.gitlab_email,
            confidence=mapping.confidence or 1.0,
            match_method=mapping.match_method or "manual",
            is_manual=True,
            project_id=mapping.project_id
        )
        
        return UserMappingResponse(
            id=str(created_mapping.id),
            run_id=str(created_mapping.run_id),
            project_id=str(created_mapping.project_id) if created_mapping.project_id else None,
            gitlab_username=created_mapping.gitlab_username,
            gitlab_email=created_mapping.gitlab_email,
            github_username=created_mapping.github_username,
            confidence=created_mapping.confidence,
            match_method=created_mapping.match_method,
            is_manual=created_mapping.is_manual,
            created_at=created_mapping.created_at.isoformat(),
            updated_at=created_mapping.updated_at.isoformat()
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user mapping: {str(e)}"
        )


@router.put("/{run_id}/user-mappings/{mapping_id}", response_model=UserMappingResponse)
async def update_user_mapping(
    run_id: str = Path(..., description="Run ID"),
    mapping_id: str = Path(..., description="Mapping ID"),
    update: UserMappingUpdate = ...,
    current_user: User = Depends(get_current_active_user)
):
    """Update a specific user mapping"""
    service = UserMappingService()
    
    try:
        updated_mapping = await service.update_mapping(
            mapping_id=mapping_id,
            github_username=update.github_username,
            is_manual=True,
            confidence=update.confidence
        )
        
        if not updated_mapping:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User mapping {mapping_id} not found"
            )
        
        return UserMappingResponse(
            id=str(updated_mapping.id),
            run_id=str(updated_mapping.run_id),
            project_id=str(updated_mapping.project_id) if updated_mapping.project_id else None,
            gitlab_username=updated_mapping.gitlab_username,
            gitlab_email=updated_mapping.gitlab_email,
            github_username=updated_mapping.github_username,
            confidence=updated_mapping.confidence,
            match_method=updated_mapping.match_method,
            is_manual=updated_mapping.is_manual,
            created_at=updated_mapping.created_at.isoformat(),
            updated_at=updated_mapping.updated_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user mapping: {str(e)}"
        )


@router.get("/{run_id}/user-mappings/{gitlab_username}", response_model=UserMappingResponse)
async def get_user_mapping(
    run_id: str = Path(..., description="Run ID"),
    gitlab_username: str = Path(..., description="GitLab username"),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific user mapping by GitLab username"""
    service = UserMappingService()
    
    try:
        mapping = await service.get_mapping(run_id, gitlab_username)
        
        if not mapping:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User mapping for {gitlab_username} not found in run {run_id}"
            )
        
        return UserMappingResponse(
            id=str(mapping.id),
            run_id=str(mapping.run_id),
            project_id=str(mapping.project_id) if mapping.project_id else None,
            gitlab_username=mapping.gitlab_username,
            gitlab_email=mapping.gitlab_email,
            github_username=mapping.github_username,
            confidence=mapping.confidence,
            match_method=mapping.match_method,
            is_manual=mapping.is_manual,
            created_at=mapping.created_at.isoformat(),
            updated_at=mapping.updated_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user mapping: {str(e)}"
        )
