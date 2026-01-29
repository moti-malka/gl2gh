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
async def test_get_run_plan_not_found(client):
    """Test getting plan for a run with no plan artifacts"""
    # Register and login
    register_data = {
        "username": "plantest",
        "email": "plantest@example.com",
        "password": "testpass123"
    }
    await client.post("/api/auth/register", json=register_data)
    
    login_data = {
        "username": "plantest",
        "password": "testpass123"
    }
    response = await client.post("/api/auth/login", json=login_data)
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create a project first
    project_data = {
        "name": "Plan Test Project",
        "description": "Test project for plan endpoint"
    }
    response = await client.post("/api/projects", json=project_data, headers=headers)
    assert response.status_code == 201
    project_id = response.json()["id"]
    
    # Create a run
    run_data = {
        "mode": "PLAN_ONLY"
    }
    response = await client.post(f"/api/projects/{project_id}/runs", json=run_data, headers=headers)
    assert response.status_code == 201
    run_id = response.json()["id"]
    
    # Try to get plan (should fail - no plan artifacts)
    response = await client.get(f"/api/runs/{run_id}/plan", headers=headers)
    assert response.status_code == 404
    assert "No plan artifacts found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_apply_run_without_project_id(client):
    """Test applying a run without specifying gitlab_project_id"""
    # Register and login
    register_data = {
        "username": "applytest",
        "email": "applytest@example.com",
        "password": "testpass123"
    }
    await client.post("/api/auth/register", json=register_data)
    
    login_data = {
        "username": "applytest",
        "password": "testpass123"
    }
    response = await client.post("/api/auth/login", json=login_data)
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create a project
    project_data = {
        "name": "Apply Test Project",
        "description": "Test project for apply endpoint"
    }
    response = await client.post("/api/projects", json=project_data, headers=headers)
    assert response.status_code == 201
    project_id = response.json()["id"]
    
    # Create a run
    run_data = {
        "mode": "APPLY"
    }
    response = await client.post(f"/api/projects/{project_id}/runs", json=run_data, headers=headers)
    assert response.status_code == 201
    run_id = response.json()["id"]
    
    # Try to apply without gitlab_project_id (should fail)
    response = await client.post(f"/api/runs/{run_id}/apply", json={}, headers=headers)
    assert response.status_code == 400
    assert "gitlab_project_id is required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_verify_run_without_project_id(client):
    """Test verifying a run without specifying gitlab_project_id"""
    # Register and login
    register_data = {
        "username": "verifytest",
        "email": "verifytest@example.com",
        "password": "testpass123"
    }
    await client.post("/api/auth/register", json=register_data)
    
    login_data = {
        "username": "verifytest",
        "password": "testpass123"
    }
    response = await client.post("/api/auth/login", json=login_data)
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create a project
    project_data = {
        "name": "Verify Test Project",
        "description": "Test project for verify endpoint"
    }
    response = await client.post("/api/projects", json=project_data, headers=headers)
    assert response.status_code == 201
    project_id = response.json()["id"]
    
    # Create a run
    run_data = {
        "mode": "FULL"
    }
    response = await client.post(f"/api/projects/{project_id}/runs", json=run_data, headers=headers)
    assert response.status_code == 201
    run_id = response.json()["id"]
    
    # Try to verify without gitlab_project_id (should fail)
    response = await client.post(f"/api/runs/{run_id}/verify", json={}, headers=headers)
    assert response.status_code == 400
    assert "gitlab_project_id is required" in response.json()["detail"]
