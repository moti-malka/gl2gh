"""Connections (credentials) endpoints"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import httpx
import logging

from app.models import User
from app.services import ConnectionService
from app.api.dependencies import require_operator
from app.api.utils import check_project_access
from app.clients.gitlab_client import GitLabClient

router = APIRouter()
logger = logging.getLogger(__name__)
import httpx

router = APIRouter()
test_router = APIRouter()  # Separate router for test endpoints


class ConnectionCreate(BaseModel):
    type: str  # "gitlab" or "github"
    base_url: Optional[str] = None
    token: str


class ConnectionResponse(BaseModel):
    id: str
    type: str
    base_url: Optional[str]
    token_last4: str
    created_at: str


class GitLabTestRequest(BaseModel):
    token: str
    base_url: Optional[str] = "https://gitlab.com"


class GitHubTestRequest(BaseModel):
    token: str


class GitLabTestResponse(BaseModel):
    valid: bool
    user: Optional[str] = None
    scopes: List[str] = []
    expires_at: Optional[str] = None
    error: Optional[str] = None


class GitHubTestResponse(BaseModel):
    valid: bool
    user: Optional[str] = None
    type: Optional[str] = None
    rate_limit: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
class ConnectionTestRequest(BaseModel):
    base_url: str
    token: str


class ConnectionTestResponse(BaseModel):
    success: bool
    user: Optional[str] = None
    scopes: Optional[List[str]] = None
    message: Optional[str] = None


class ConnectionCreateGeneral(BaseModel):
    type: str  # "gitlab" or "github"
    url: Optional[str] = None
    token: str
    name: Optional[str] = None


@router.post("/{project_id}/connections", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_connection(
    project_id: str,
    connection: ConnectionCreateGeneral,
    current_user: User = Depends(require_operator)
):
    """Add connection to project (generic endpoint)"""
    await check_project_access(project_id, current_user)
    
    connection_service = ConnectionService()
    
    try:
        # Delegate to specific handler based on type
        if connection.type == "gitlab":
            conn = await connection_service.store_gitlab_connection(
                project_id=project_id,
                token=connection.token,
                base_url=connection.url or "https://gitlab.com"
            )
        elif connection.type == "github":
            conn = await connection_service.store_github_connection(
                project_id=project_id,
                token=connection.token,
                base_url=connection.url
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid connection type: {connection.type}. Must be 'gitlab' or 'github'"
            )
        
        return ConnectionResponse(
            id=str(conn.id),
            type=conn.type,
            base_url=conn.base_url,
            token_last4=conn.token_last4,
            created_at=conn.created_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create connection: {str(e)}"
        )


@router.post("/{project_id}/connections/gitlab", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_gitlab_connection(
    project_id: str,
    connection: ConnectionCreate,
    current_user: User = Depends(require_operator)
):
    """Add GitLab connection to project"""
    await check_project_access(project_id, current_user)
    
    connection_service = ConnectionService()
    
    try:
        conn = await connection_service.store_gitlab_connection(
            project_id=project_id,
            token=connection.token,
            base_url=connection.base_url
        )
        
        return ConnectionResponse(
            id=str(conn.id),
            type=conn.type,
            base_url=conn.base_url,
            token_last4=conn.token_last4,
            created_at=conn.created_at.isoformat()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create connection: {str(e)}"
        )


@router.post("/{project_id}/connections/github", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_github_connection(
    project_id: str,
    connection: ConnectionCreate,
    current_user: User = Depends(require_operator)
):
    """Add GitHub connection to project"""
    await check_project_access(project_id, current_user)
    
    connection_service = ConnectionService()
    
    try:
        conn = await connection_service.store_github_connection(
            project_id=project_id,
            token=connection.token,
            base_url=connection.base_url
        )
        
        return ConnectionResponse(
            id=str(conn.id),
            type=conn.type,
            base_url=conn.base_url,
            token_last4=conn.token_last4,
            created_at=conn.created_at.isoformat()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create connection: {str(e)}"
        )


@router.get("/{project_id}/connections", response_model=List[ConnectionResponse])
async def list_connections(
    project_id: str,
    current_user: User = Depends(require_operator)
):
    """List all connections for a project"""
    await check_project_access(project_id, current_user)
    
    connection_service = ConnectionService()
    connections = await connection_service.get_connections(project_id)
    
    return [
        ConnectionResponse(
            id=str(c.id),
            type=c.type,
            base_url=c.base_url,
            token_last4=c.token_last4,
            created_at=c.created_at.isoformat()
        )
        for c in connections
    ]


@router.delete("/{project_id}/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    project_id: str,
    connection_id: str,
    current_user: User = Depends(require_operator)
):
    """Delete a connection"""
    await check_project_access(project_id, current_user)
    
    connection_service = ConnectionService()
    success = await connection_service.delete_connection(connection_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found"
        )
    
    return None


@router.post("/{project_id}/connections/{connection_id}/test")
async def test_connection_by_id(
    project_id: str,
    connection_id: str,
    current_user: User = Depends(require_operator)
):
    """Test a connection by its ID"""
    await check_project_access(project_id, current_user)
    
    connection_service = ConnectionService()
    
    # Get all connections and find by ID
    connections = await connection_service.get_connections(project_id)
    conn = None
    for c in connections:
        if str(c.id) == connection_id:
            conn = c
            break
    
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found"
        )
    
    # Get decrypted token
    token = await connection_service.get_decrypted_token(connection_id, project_id)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not decrypt connection token"
        )
    
    # Test based on connection type
    if conn.type == "gitlab":
        try:
            client = GitLabClient(
                base_url=conn.base_url or "https://gitlab.com",
                token=token
            )
            user_info = await client.get_current_user()
            return {
                "valid": True,
                "user": user_info.get("username"),
                "message": f"Successfully connected as {user_info.get('username')}"
            }
        except Exception as e:
            return {
                "valid": False,
                "error": str(e)
            }
    elif conn.type == "github":
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.github.com/user",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json"
                    }
                )
                if response.status_code == 200:
                    user_data = response.json()
                    return {
                        "valid": True,
                        "user": user_data.get("login"),
                        "message": f"Successfully connected as {user_data.get('login')}"
                    }
                else:
                    return {
                        "valid": False,
                        "error": f"GitHub API returned {response.status_code}"
                    }
        except Exception as e:
            return {
                "valid": False,
                "error": str(e)
            }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown connection type: {conn.type}"
        )


@router.post("/{project_id}/connections/gitlab/test", response_model=GitLabTestResponse)
async def test_gitlab_connection(
    project_id: str,
    request: GitLabTestRequest,
    current_user: User = Depends(require_operator)
):
    """
    Test GitLab connection by validating the token against GitLab API.
    
    Args:
        project_id: Project ID (used for access control)
        request: GitLab test request containing token and base_url
        current_user: Current authenticated user
        
    Returns:
        GitLabTestResponse with validation results
    """
    await check_project_access(project_id, current_user)
    
    try:
        # Initialize GitLab client with provided credentials
        base_url = request.base_url or "https://gitlab.com"
        
        async with GitLabClient(base_url, request.token, timeout=10) as client:
            # Test connection by getting current user
            user_info = await client.get_current_user()
            
            # Extract scopes from token (if available in headers)
            # Note: GitLab doesn't provide scopes in the user response,
            # but we can infer successful API access
            scopes = []
            
            return GitLabTestResponse(
                valid=True,
                user=user_info.get("username"),
                scopes=scopes,
                expires_at=None  # GitLab tokens don't have expiration in API response
            )
            
    except httpx.HTTPStatusError as e:
        # Handle HTTP errors (e.g., 401 Unauthorized, 403 Forbidden)
        error_detail = f"HTTP {e.response.status_code}"
        if e.response.status_code == 401:
            error_detail = "Invalid token or insufficient permissions"
        elif e.response.status_code == 403:
            error_detail = "Token does not have required scopes"
        
        logger.info(f"GitLab connection test failed for project {project_id}: {error_detail}")
        return GitLabTestResponse(
            valid=False,
            error=error_detail
        )
        
    except httpx.RequestError as e:
        # Handle network errors
        logger.warning(f"GitLab connection test network error for project {project_id}: {str(e)}")
        return GitLabTestResponse(
            valid=False,
            error=f"Connection failed: {str(e)}"
        )
        
    except Exception as e:
        # Handle other errors - log full error but return generic message
        logger.error(f"Unexpected error testing GitLab connection for project {project_id}: {str(e)}")
        return GitLabTestResponse(
            valid=False,
            error="An unexpected error occurred while testing the connection"
        )


@router.post("/{project_id}/connections/github/test", response_model=GitHubTestResponse)
async def test_github_connection(
    project_id: str,
    request: GitHubTestRequest,
    current_user: User = Depends(require_operator)
):
    """
    Test GitHub connection by validating the token against GitHub API.
    
    Args:
        project_id: Project ID (used for access control)
        request: GitHub test request containing token
        current_user: Current authenticated user
        
    Returns:
        GitHubTestResponse with validation results
    """
    await check_project_access(project_id, current_user)
    
    try:
        # Test connection using GitHub API /user endpoint
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {request.token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                },
                timeout=10.0
            )
            
            if response.status_code == 200:
                try:
                    user_data = response.json()
                except Exception as json_error:
                    logger.error(f"Failed to parse GitHub API response for project {project_id}: {str(json_error)}")
                    return GitHubTestResponse(
                        valid=False,
                        error="Failed to parse API response"
                    )
                
                # Extract rate limit information from headers
                rate_limit_info = None
                if "X-RateLimit-Remaining" in response.headers:
                    rate_limit_info = {
                        "remaining": int(response.headers.get("X-RateLimit-Remaining", 0)),
                        "reset_at": response.headers.get("X-RateLimit-Reset", None)
                    }
                
                # Determine if user or organization
                account_type = "organization" if user_data.get("type") == "Organization" else "user"
                
                return GitHubTestResponse(
                    valid=True,
                    user=user_data.get("login"),
                    type=account_type,
                    rate_limit=rate_limit_info
                )
            else:
                # Handle non-200 responses
                error_detail = f"HTTP {response.status_code}"
                if response.status_code == 401:
                    error_detail = "Invalid token or token has expired"
                elif response.status_code == 403:
                    error_detail = "Token does not have required permissions"
                
                logger.info(f"GitHub connection test failed for project {project_id}: {error_detail}")
                return GitHubTestResponse(
                    valid=False,
                    error=error_detail
                )
                
    except httpx.RequestError as e:
        # Handle network errors
        logger.warning(f"GitHub connection test network error for project {project_id}: {str(e)}")
        return GitHubTestResponse(
            valid=False,
            error=f"Connection failed: {str(e)}"
        )
        
    except Exception as e:
        # Handle other errors - log full error but return generic message
        logger.error(f"Unexpected error testing GitHub connection for project {project_id}: {str(e)}")
        return GitHubTestResponse(
            valid=False,
            error="An unexpected error occurred while testing the connection"
        )

@test_router.post("/connections/test/gitlab", response_model=ConnectionTestResponse)
async def test_gitlab_connection(
    request: ConnectionTestRequest,
    current_user: User = Depends(require_operator)
):
    """Test GitLab connection without saving it"""
    try:
        # Use default GitLab URL if not provided
        base_url = request.base_url or "https://gitlab.com"
        
        # Create GitLab client and test connection
        async with GitLabClient(base_url=base_url, token=request.token, timeout=10) as client:
            # Try to get current user information
            user_data = await client.get_current_user()
            
            # Extract username
            username = user_data.get("username")
            
            # Note: GitLab API doesn't expose token scopes in the response
            # We can only confirm the connection works
            
            return ConnectionTestResponse(
                success=True,
                user=username,
                scopes=None,
                message="Connection successful"
            )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return ConnectionTestResponse(
                success=False,
                message="Invalid token or insufficient permissions"
            )
        else:
            return ConnectionTestResponse(
                success=False,
                message=f"GitLab API error: {e.response.status_code}"
            )
    except httpx.RequestError as e:
        return ConnectionTestResponse(
            success=False,
            message=f"Connection error: Unable to reach GitLab server"
        )
    except Exception as e:
        return ConnectionTestResponse(
            success=False,
            message=f"Unexpected error: {str(e)}"
        )


@test_router.get("/connections/test/gitlab/browse")
async def browse_gitlab_direct(
    base_url: str,
    token: str,
    path: Optional[str] = None,
    include_projects: bool = True,
    current_user: User = Depends(require_operator)
):
    """
    Browse GitLab groups and projects directly with credentials.
    Used during project creation wizard before project exists.
    """
    async with GitLabClient(base_url=base_url, token=token) as client:
        try:
            items = []
            parent_path = None
            
            if path:
                # Browse specific group
                try:
                    group = await client.get_group(path)
                    parent_path = "/".join(path.split("/")[:-1]) if "/" in path else None
                    
                    # Get subgroups
                    subgroups = await client.list_subgroups(path, max_pages=10)
                    for sg in subgroups:
                        items.append({
                            "id": sg["id"],
                            "name": sg["name"],
                            "full_path": sg["full_path"],
                            "description": sg.get("description"),
                            "visibility": sg.get("visibility"),
                            "type": "group"
                        })
                    
                    # Get projects if requested
                    if include_projects:
                        projects = await client.list_group_projects(path, include_subgroups=False, max_pages=10)
                        for proj in projects:
                            items.append({
                                "id": proj["id"],
                                "name": proj["name"],
                                "full_path": proj["path_with_namespace"],
                                "description": proj.get("description"),
                                "visibility": proj.get("visibility"),
                                "type": "project",
                                "default_branch": proj.get("default_branch"),
                            })
                except Exception as e:
                    logger.warning(f"Could not browse path {path}: {e}")
                    return {
                        "success": False,
                        "items": [],
                        "error": f"Group not found: {path}"
                    }
            else:
                # Get top-level groups
                groups = await client.list_groups(top_level_only=True, max_pages=10)
                for g in groups:
                    items.append({
                        "id": g["id"],
                        "name": g["name"],
                        "full_path": g["full_path"],
                        "description": g.get("description"),
                        "visibility": g.get("visibility"),
                        "type": "group"
                    })
                
                # Also include user's personal projects
                if include_projects:
                    user_projects = await client.list_projects(membership=True, max_pages=5)
                    for proj in user_projects:
                        namespace = proj.get("namespace", {})
                        if namespace.get("kind") == "user":
                            items.append({
                                "id": proj["id"],
                                "name": proj["name"],
                                "full_path": proj["path_with_namespace"],
                                "description": proj.get("description"),
                                "visibility": proj.get("visibility"),
                                "type": "project",
                                "default_branch": proj.get("default_branch"),
                            })
            
            return {
                "success": True,
                "items": items,
                "current_path": path,
                "parent_path": parent_path
            }
            
        except Exception as e:
            logger.error(f"Error browsing GitLab: {e}")
            return {
                "success": False,
                "items": [],
                "error": str(e)
            }


@test_router.post("/connections/test/github", response_model=ConnectionTestResponse)
async def test_github_connection(
    request: ConnectionTestRequest,
    current_user: User = Depends(require_operator)
):
    """Test GitHub connection without saving it"""
    try:
        # Use default GitHub API URL if not provided
        base_url = request.base_url or "https://api.github.com"
        
        # Create HTTP client and test connection
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{base_url}/user",
                headers={
                    "Authorization": f"token {request.token}",
                    "Accept": "application/vnd.github.v3+json"
                }
            )
            response.raise_for_status()
            user_data = response.json()
            
            # Extract username (login)
            username = user_data.get("login")
            
            # Get token scopes from response headers
            scopes = None
            if "X-OAuth-Scopes" in response.headers:
                scopes = [s.strip() for s in response.headers["X-OAuth-Scopes"].split(",") if s.strip()]
            
            return ConnectionTestResponse(
                success=True,
                user=username,
                scopes=scopes,
                message="Connection successful"
            )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return ConnectionTestResponse(
                success=False,
                message="Invalid token or insufficient permissions"
            )
        else:
            return ConnectionTestResponse(
                success=False,
                message=f"GitHub API error: {e.response.status_code}"
            )
    except httpx.RequestError as e:
        return ConnectionTestResponse(
            success=False,
            message=f"Connection error: Unable to reach GitHub server"
        )
    except Exception as e:
        return ConnectionTestResponse(
            success=False,
            message=f"Unexpected error: {str(e)}"
        )


# ===== GitLab Browse Endpoints =====

class GitLabBrowseItem(BaseModel):
    id: int
    name: str
    full_path: str
    description: Optional[str] = None
    visibility: Optional[str] = None
    type: str  # "group", "project", or "root"
    children: Optional[List["GitLabBrowseItem"]] = None
    default_branch: Optional[str] = None
    last_activity_at: Optional[str] = None


class GitLabBrowseResponse(BaseModel):
    success: bool
    items: List[GitLabBrowseItem] = []
    current_path: Optional[str] = None
    parent_path: Optional[str] = None
    error: Optional[str] = None


class GitLabScopeRequest(BaseModel):
    scope_type: str  # "group" or "project"
    scope_id: int
    scope_path: str


@router.get("/{project_id}/connections/gitlab/browse")
async def browse_gitlab(
    project_id: str,
    path: Optional[str] = None,
    include_projects: bool = True,
    current_user: User = Depends(require_operator)
):
    """
    Browse GitLab groups and projects.
    
    - If path is None, returns top-level groups
    - If path is a group, returns subgroups and projects within
    """
    from app.services.connection_service import ConnectionService
    
    await check_project_access(project_id, current_user)
    
    connection_service = ConnectionService()
    
    # Get GitLab connection
    gitlab_conn = await connection_service.get_connection_by_type(project_id, "gitlab")
    if not gitlab_conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GitLab connection not found. Please add GitLab credentials first."
        )
    
    # Get decrypted token
    token = await connection_service.get_decrypted_token(str(gitlab_conn.id), project_id)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve GitLab token"
        )
    
    base_url = gitlab_conn.base_url or "https://gitlab.com"
    
    async with GitLabClient(base_url=base_url, token=token) as client:
        try:
            items = []
            parent_path = None
            
            if path:
                # Browse specific group
                try:
                    group = await client.get_group(path)
                    parent_path = "/".join(path.split("/")[:-1]) if "/" in path else None
                    
                    # Get subgroups
                    subgroups = await client.list_subgroups(path, max_pages=10)
                    for sg in subgroups:
                        items.append({
                            "id": sg["id"],
                            "name": sg["name"],
                            "full_path": sg["full_path"],
                            "description": sg.get("description"),
                            "visibility": sg.get("visibility"),
                            "type": "group"
                        })
                    
                    # Get projects if requested
                    if include_projects:
                        projects = await client.list_group_projects(path, include_subgroups=False, max_pages=10)
                        for proj in projects:
                            items.append({
                                "id": proj["id"],
                                "name": proj["name"],
                                "full_path": proj["path_with_namespace"],
                                "description": proj.get("description"),
                                "visibility": proj.get("visibility"),
                                "type": "project",
                                "default_branch": proj.get("default_branch"),
                                "last_activity_at": proj.get("last_activity_at"),
                            })
                except Exception as e:
                    logger.warning(f"Could not browse path {path}: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Group not found: {path}"
                    )
            else:
                # Get top-level groups
                groups = await client.list_groups(top_level_only=True, max_pages=10)
                for g in groups:
                    items.append({
                        "id": g["id"],
                        "name": g["name"],
                        "full_path": g["full_path"],
                        "description": g.get("description"),
                        "visibility": g.get("visibility"),
                        "type": "group"
                    })
                
                # Also include user's personal projects (not in any group)
                if include_projects:
                    user = await client.get_current_user()
                    user_projects = await client.list_projects(membership=True, max_pages=5)
                    for proj in user_projects:
                        # Only include projects at user namespace level
                        namespace = proj.get("namespace", {})
                        if namespace.get("kind") == "user":
                            items.append({
                                "id": proj["id"],
                                "name": proj["name"],
                                "full_path": proj["path_with_namespace"],
                                "description": proj.get("description"),
                                "visibility": proj.get("visibility"),
                                "type": "project",
                                "default_branch": proj.get("default_branch"),
                                "last_activity_at": proj.get("last_activity_at"),
                            })
            
            return {
                "success": True,
                "items": items,
                "current_path": path,
                "parent_path": parent_path
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error browsing GitLab: {e}")
            return {
                "success": False,
                "items": [],
                "error": str(e)
            }


@router.post("/{project_id}/connections/gitlab/set-scope")
async def set_migration_scope(
    project_id: str,
    scope: GitLabScopeRequest,
    current_user: User = Depends(require_operator)
):
    """
    Set the migration scope for a project.
    
    This defines what GitLab group or project will be migrated.
    """
    from app.services import ProjectService
    
    await check_project_access(project_id, current_user)
    
    project_service = ProjectService()
    
    # Update project settings with the scope
    updates = {
        "settings": {
            "gitlab": {
                "scope_type": scope.scope_type,
                "scope_id": scope.scope_id,
                "scope_path": scope.scope_path
            }
        }
    }
    
    updated = await project_service.update_project(project_id, updates)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update project scope"
        )
    
    return {
        "success": True,
        "message": f"Migration scope set to {scope.scope_type}: {scope.scope_path}",
        "scope": scope.model_dump()
    }


@router.get("/{project_id}/connections/gitlab/scope")
async def get_migration_scope(
    project_id: str,
    current_user: User = Depends(require_operator)
):
    """Get the current migration scope for a project."""
    from app.services import ProjectService
    
    await check_project_access(project_id, current_user)
    
    project_service = ProjectService()
    project = await project_service.get_project(project_id)
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    gitlab_settings = project.settings.gitlab if project.settings else None
    
    if not gitlab_settings or not gitlab_settings.get("scope_type"):
        return {
            "has_scope": False,
            "scope": None
        }
    
    return {
        "has_scope": True,
        "scope": {
            "scope_type": gitlab_settings.get("scope_type"),
            "scope_id": gitlab_settings.get("scope_id"),
            "scope_path": gitlab_settings.get("scope_path")
        }
    }
