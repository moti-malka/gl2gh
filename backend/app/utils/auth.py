"""Authentication utilities and JWT token handling"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError

from app.config import settings
from app.utils.security import create_access_token as create_jwt_token, decode_access_token
from app.models import User
from app.services.user_service import UserService


def create_access_token(user_id: str, role: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token for user
    
    Args:
        user_id: User ID
        role: User role
        expires_delta: Optional custom expiration time
        
    Returns:
        JWT token string
    """
    data = {
        "sub": user_id,
        "role": role,
        "type": "access"
    }
    return create_jwt_token(data, expires_delta)


def create_refresh_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT refresh token for user
    
    Args:
        user_id: User ID
        expires_delta: Optional custom expiration time (default: 7 days)
        
    Returns:
        JWT refresh token string
    """
    if expires_delta is None:
        expires_delta = timedelta(days=7)
    
    data = {
        "sub": user_id,
        "type": "refresh"
    }
    return create_jwt_token(data, expires_delta)


def verify_token(token: str) -> Optional[dict]:
    """
    Verify and decode JWT token
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload if valid, None otherwise
    """
    return decode_access_token(token)


async def get_current_user(token: str) -> Optional[User]:
    """
    Get current user from JWT token
    
    Args:
        token: JWT token string
        
    Returns:
        User object if token is valid and user exists, None otherwise
    """
    payload = verify_token(token)
    if not payload:
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        return None
    
    # Fetch user from database
    user_service = UserService()
    user = await user_service.get_user_by_id(user_id)
    
    if not user or not user.is_active:
        return None
    
    return user


async def authenticate_user(username_or_email: str, password: str) -> Optional[User]:
    """
    Authenticate user with username/email and password
    
    Args:
        username_or_email: Username or email
        password: Plain text password
        
    Returns:
        User object if authentication successful, None otherwise
    """
    user_service = UserService()
    
    # Try to find user by email first, then username
    user = await user_service.get_user_by_email(username_or_email)
    if not user:
        user = await user_service.get_user_by_username(username_or_email)
    
    if not user:
        return None
    
    # Verify password
    if not user_service.verify_password(user, password):
        return None
    
    # Check if user is active
    if not user.is_active:
        return None
    
    return user
