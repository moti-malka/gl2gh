"""Authentication endpoints"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.models import User
from app.utils.auth import authenticate_user, create_access_token, create_refresh_token, verify_token
from app.services import UserService
from app.api.dependencies import get_current_active_user

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    full_name: Optional[str] = None
    is_active: bool


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """
    Authenticate user and return JWT token
    """
    user = await authenticate_user(request.username, request.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create tokens
    access_token = create_access_token(str(user.id), user.role)
    refresh_token = create_refresh_token(str(user.id))
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest):
    """
    Refresh access token using refresh token
    """
    payload = verify_token(request.refresh_token)
    
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Get user to verify they still exist and get current role
    user_service = UserService()
    user = await user_service.get_user_by_id(user_id)
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Create new tokens
    access_token = create_access_token(str(user.id), user.role)
    new_refresh_token = create_refresh_token(str(user.id))
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token
    )


@router.post("/logout")
async def logout():
    """
    Logout user
    
    Note: JWT tokens are stateless, so logout is handled client-side by discarding the token.
    For production, consider implementing a token blacklist.
    """
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_active_user)):
    """
    Get current authenticated user
    """
    return UserResponse(
        id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        full_name=current_user.full_name,
        is_active=current_user.is_active
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest):
    """
    Register a new user
    
    Note: In production, you may want to restrict this endpoint or add email verification.
    """
    user_service = UserService()
    
    try:
        user = await user_service.create_user(
            email=request.email,
            username=request.username,
            password=request.password,
            full_name=request.full_name,
            role="operator"  # Default role
        )
        
        return UserResponse(
            id=str(user.id),
            username=user.username,
            email=user.email,
            role=user.role,
            full_name=user.full_name,
            is_active=user.is_active
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )
