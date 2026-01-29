"""FastAPI dependencies for authentication and authorization"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.models import User
from app.utils.auth import get_current_user as get_user_from_token


# HTTP Bearer security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    Dependency to get current authenticated user
    
    Args:
        credentials: HTTP Bearer token credentials
        
    Returns:
        Current user
        
    Raises:
        HTTPException: If authentication fails
    """
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
