"""Integration tests for API endpoints"""

import pytest
from httpx import AsyncClient
from app.main import app
from app.db import connect_to_mongo, close_mongo_connection


@pytest.fixture(scope="module")
async def client():
    """Create test client"""
    await connect_to_mongo()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    await close_mongo_connection()


@pytest.mark.asyncio
async def test_health_check(client):
    """Test health check endpoint"""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_root_endpoint(client):
    """Test root endpoint"""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_register_and_login(client):
    """Test user registration and login flow"""
    # Register new user
    register_data = {
        "username": "apitest",
        "email": "apitest@example.com",
        "password": "testpass123",
        "full_name": "API Test User"
    }
    
    response = await client.post("/api/auth/register", json=register_data)
    assert response.status_code == 201
    user_data = response.json()
    assert user_data["username"] == "apitest"
    assert user_data["email"] == "apitest@example.com"
    
    # Login
    login_data = {
        "username": "apitest",
        "password": "testpass123"
    }
    
    response = await client.post("/api/auth/login", json=login_data)
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    
    return token_data["access_token"]


@pytest.mark.asyncio
async def test_get_me_authenticated(client):
    """Test getting current user with authentication"""
    # First register and login
    register_data = {
        "username": "metest",
        "email": "metest@example.com",
        "password": "testpass123"
    }
    await client.post("/api/auth/register", json=register_data)
    
    login_data = {
        "username": "metest",
        "password": "testpass123"
    }
    response = await client.post("/api/auth/login", json=login_data)
    token = response.json()["access_token"]
    
    # Get current user
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    user_data = response.json()
    assert user_data["username"] == "metest"


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client):
    """Test getting current user without authentication"""
    response = await client.get("/api/auth/me")
    assert response.status_code == 403  # No authorization header


@pytest.mark.asyncio
async def test_create_project_flow(client):
    """Test complete project creation flow"""
    # Register and login
    register_data = {
        "username": "projecttest",
        "email": "projecttest@example.com",
        "password": "testpass123"
    }
    await client.post("/api/auth/register", json=register_data)
    
    login_data = {
        "username": "projecttest",
        "password": "testpass123"
    }
    response = await client.post("/api/auth/login", json=login_data)
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create project
    project_data = {
        "name": "API Test Project",
        "description": "Created via API test"
    }
    response = await client.post("/api/projects", json=project_data, headers=headers)
    assert response.status_code == 201
    project = response.json()
    assert project["name"] == "API Test Project"
    project_id = project["id"]
    
    # Get project
    response = await client.get(f"/api/projects/{project_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "API Test Project"
    
    # List projects
    response = await client.get("/api/projects", headers=headers)
    assert response.status_code == 200
    projects = response.json()
    assert len(projects) >= 1
    
    return project_id, token


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    """Test login with wrong password"""
    # Register user
    register_data = {
        "username": "wrongpass",
        "email": "wrongpass@example.com",
        "password": "correctpass"
    }
    await client.post("/api/auth/register", json=register_data)
    
    # Try to login with wrong password
    login_data = {
        "username": "wrongpass",
        "password": "wrongpassword"
    }
    response = await client.post("/api/auth/login", json=login_data)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_run_dispatches_task(client):
    """Test that creating a run dispatches the Celery task"""
    from unittest.mock import Mock, patch
    
    # Register and login
    register_data = {
        "username": "runtest",
        "email": "runtest@example.com",
        "password": "testpass123"
    }
    await client.post("/api/auth/register", json=register_data)
    
    login_data = {
        "username": "runtest",
        "password": "testpass123"
    }
    response = await client.post("/api/auth/login", json=login_data)
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create project
    project_data = {
        "name": "Run Test Project",
        "description": "For testing run creation"
    }
    response = await client.post("/api/projects", json=project_data, headers=headers)
    assert response.status_code == 201
    project_id = response.json()["id"]
    
    # Mock the Celery task
    with patch('app.api.runs.run_migration') as mock_task:
        mock_task.delay = Mock()
        
        # Create run
        run_data = {
            "mode": "PLAN_ONLY",
            "deep": True,
            "deep_top_n": 20
        }
        response = await client.post(
            f"/api/projects/{project_id}/runs",
            json=run_data,
            headers=headers
        )
        
        # Verify response
        assert response.status_code == 201
        run_response = response.json()
        assert run_response["status"] == "CREATED"
        assert run_response["mode"] == "PLAN_ONLY"
        
        # Verify task was dispatched with correct parameters
        mock_task.delay.assert_called_once()
        call_args = mock_task.delay.call_args[0]
        assert call_args[0] == run_response["id"]  # run_id
        assert call_args[1] == "PLAN_ONLY"  # mode
        assert call_args[2]["deep"] is True  # config
        assert call_args[2]["deep_top_n"] == 20  # config


@pytest.mark.asyncio
async def test_resume_run_dispatches_task(client):
    """Test that resuming a run dispatches the Celery task"""
    from unittest.mock import Mock, patch
    
    # Register and login
    register_data = {
        "username": "resumetest",
        "email": "resumetest@example.com",
        "password": "testpass123"
    }
    await client.post("/api/auth/register", json=register_data)
    
    login_data = {
        "username": "resumetest",
        "password": "testpass123"
    }
    response = await client.post("/api/auth/login", json=login_data)
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create project
    project_data = {
        "name": "Resume Test Project",
        "description": "For testing run resume"
    }
    response = await client.post("/api/projects", json=project_data, headers=headers)
    project_id = response.json()["id"]
    
    # Mock the Celery task for create_run
    with patch('app.api.runs.run_migration') as mock_task:
        mock_task.delay = Mock()
        
        # Create run
        run_data = {"mode": "FULL"}
        response = await client.post(
            f"/api/projects/{project_id}/runs",
            json=run_data,
            headers=headers
        )
        run_id = response.json()["id"]
    
    # Simulate run failure by updating run status directly
    from app.services import RunService
    run_service = RunService()
    await run_service.update_run_status(run_id, "FAILED", stage="DISCOVER")
    
    # Mock the Celery task for resume
    with patch('app.api.runs.run_migration') as mock_task:
        mock_task.delay = Mock()
        
        # Resume run
        response = await client.post(
            f"/api/runs/{run_id}/resume",
            json={},
            headers=headers
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["message"] == "Run resumed successfully"
        
        # Verify task was dispatched with correct parameters
        mock_task.delay.assert_called_once()
        call_args = mock_task.delay.call_args[0]
        assert call_args[0] == run_id  # run_id
        assert call_args[1] == "FULL"  # mode
        assert isinstance(call_args[2], dict)  # config_snapshot
