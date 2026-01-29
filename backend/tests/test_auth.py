"""Tests for authentication utilities"""

import pytest
from app.utils.auth import (
    create_access_token,
    create_refresh_token,
    verify_token,
    authenticate_user
)


@pytest.mark.asyncio
async def test_create_and_verify_access_token():
    """Test JWT access token creation and verification"""
    user_id = "507f1f77bcf86cd799439011"
    role = "operator"
    
    token = create_access_token(user_id, role)
    assert token is not None
    
    payload = verify_token(token)
    assert payload is not None
    assert payload["sub"] == user_id
    assert payload["role"] == role
    assert payload["type"] == "access"


@pytest.mark.asyncio
async def test_create_and_verify_refresh_token():
    """Test JWT refresh token creation and verification"""
    user_id = "507f1f77bcf86cd799439011"
    
    token = create_refresh_token(user_id)
    assert token is not None
    
    payload = verify_token(token)
    assert payload is not None
    assert payload["sub"] == user_id
    assert payload["type"] == "refresh"


@pytest.mark.asyncio
async def test_verify_invalid_token():
    """Test verification of invalid token"""
    payload = verify_token("invalid-token")
    assert payload is None


@pytest.mark.asyncio
async def test_authenticate_user_success(test_user):
    """Test successful user authentication"""
    user = await authenticate_user("testuser", "testpass123")
    assert user is not None
    assert user.username == "testuser"
    
    # Also test with email
    user = await authenticate_user("test@example.com", "testpass123")
    assert user is not None
    assert user.email == "test@example.com"


@pytest.mark.asyncio
async def test_authenticate_user_wrong_password(test_user):
    """Test authentication with wrong password"""
    user = await authenticate_user("testuser", "wrongpassword")
    assert user is None


@pytest.mark.asyncio
async def test_authenticate_user_not_found():
    """Test authentication with non-existent user"""
    user = await authenticate_user("nonexistent", "password")
    assert user is None
