"""Tests for UserService"""

import pytest


@pytest.mark.asyncio
async def test_create_user(user_service):
    """Test user creation"""
    user = await user_service.create_user(
        email="newuser@example.com",
        username="newuser",
        password="password123",
        role="operator"
    )
    
    assert user.email == "newuser@example.com"
    assert user.username == "newuser"
    assert user.role == "operator"
    assert user.is_active is True
    assert user.id is not None


@pytest.mark.asyncio
async def test_create_duplicate_user(user_service, test_user):
    """Test that creating duplicate user raises error"""
    with pytest.raises(ValueError):
        await user_service.create_user(
            email=test_user.email,
            username="different",
            password="password123"
        )


@pytest.mark.asyncio
async def test_get_user_by_id(user_service, test_user):
    """Test getting user by ID"""
    user = await user_service.get_user_by_id(str(test_user.id))
    assert user is not None
    assert user.email == test_user.email
    assert user.username == test_user.username


@pytest.mark.asyncio
async def test_get_user_by_email(user_service, test_user):
    """Test getting user by email"""
    user = await user_service.get_user_by_email(test_user.email)
    assert user is not None
    assert str(user.id) == str(test_user.id)


@pytest.mark.asyncio
async def test_get_user_by_username(user_service, test_user):
    """Test getting user by username"""
    user = await user_service.get_user_by_username(test_user.username)
    assert user is not None
    assert str(user.id) == str(test_user.id)


@pytest.mark.asyncio
async def test_update_user(user_service, test_user):
    """Test updating user"""
    updated = await user_service.update_user(
        str(test_user.id),
        {"full_name": "Test User Full"}
    )
    
    assert updated is not None
    assert updated.full_name == "Test User Full"


@pytest.mark.asyncio
async def test_delete_user(user_service, test_user):
    """Test deleting user"""
    success = await user_service.delete_user(str(test_user.id))
    assert success is True
    
    # Verify user is deleted
    user = await user_service.get_user_by_id(str(test_user.id))
    assert user is None


@pytest.mark.asyncio
async def test_list_users(user_service, test_user, test_admin):
    """Test listing users"""
    users = await user_service.list_users(skip=0, limit=10)
    assert len(users) >= 2
    
    emails = {u.email for u in users}
    assert test_user.email in emails
    assert test_admin.email in emails


@pytest.mark.asyncio
async def test_verify_password(user_service, test_user):
    """Test password verification"""
    # Correct password
    assert user_service.verify_password(test_user, "testpass123") is True
    
    # Incorrect password
    assert user_service.verify_password(test_user, "wrongpassword") is False
