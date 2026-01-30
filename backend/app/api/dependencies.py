"""FastAPI dependencies for authentication and authorization"""

from typing import Optional
from datetime import datetime
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from bson import ObjectId

from app.models import User
from app.utils.auth import get_current_user as get_user_from_token
from app.config import settings


# HTTP Bearer security scheme
security = HTTPBearer(auto_error=False)

# Dev user for development mode
DEV_USER = User(
    id=ObjectId("000000000000000000000000"),
    email="dev@gl2gh.local",
    username="dev",
    hashed_password="dev-no-password",
    role="admin",
    is_active=True,
    created_at=datetime.utcnow(),
    updated_at=datetime.utcnow()
)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> User:
    """
    Dependency to get current authenticated user
    
    In development mode (DEBUG=True), allows bypass with X-Dev-Bypass header
    or returns a dev user if no credentials provided.
    
    Args:
        request: HTTP request
        credentials: HTTP Bearer token credentials
        
    Returns:
        Current user
        
    Raises:
        HTTPException: If authentication fails
    """
    # Dev mode bypass
    if settings.DEBUG:
        # Check for X-Dev-Bypass header
        if request.headers.get("X-Dev-Bypass") == "true":
            return DEV_USER
        # If no credentials in dev mode, return dev user
        if not credentials:
            return DEV_USER
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    user = await get_user_from_token(token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to get current active user
    
    Args:
        current_user: Current user from get_current_user
        
    Returns:
        Current active user
        
    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


async def require_admin(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Dependency to require admin role
    
    Args:
        current_user: Current active user
        
    Returns:
        Current user if admin
        
    Raises:
        HTTPException: If user is not admin
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


async def require_operator(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Dependency to require operator or admin role
    
    Args:
        current_user: Current active user
        
    Returns:
        Current user if operator or admin
        
    Raises:
        HTTPException: If user is not operator or admin
    """
    if current_user.role not in ["operator", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator or admin access required"
        )
    return current_user


# Optional authentication (for endpoints that work with or without auth)
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[User]:
    """
    Dependency to optionally get current user
    
    Args:
        credentials: Optional HTTP Bearer token credentials
        
    Returns:
        Current user if authenticated, None otherwise
    """
    if not credentials:
        return None
    
    token = credentials.credentials
    user = await get_user_from_token(token)
    return user
