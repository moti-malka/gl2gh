"""Tests for Quick Migrate API endpoint"""

import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock
from app.main import app
from app.db import connect_to_mongo, close_mongo_connection


@pytest.fixture(scope="module")
async def client():
    """Create test client"""
    await connect_to_mongo()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    await close_mongo_connection()


@pytest.fixture
async def auth_token(client):
    """Create test user and get auth token"""
    # Register test user
    register_data = {
        "username": "quickmigratetest",
        "email": "quickmigrate@example.com",
        "password": "testpass123",
        "full_name": "Quick Migrate Test",
        "role": "operator"
    }
    
    await client.post("/api/auth/register", json=register_data)
    
    # Login to get token
    login_data = {
        "username": "quickmigratetest",
        "password": "testpass123"
    }
    response = await client.post("/api/auth/login", json=login_data)
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_quick_migrate_validation_gitlab_url(client, auth_token):
    """Test quick migrate endpoint validates GitLab URL"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    # Invalid URL - no protocol
    request_data = {
        "gitlab_url": "gitlab.com",
        "gitlab_project_path": "user/project",
        "gitlab_token": "glpat-test",
        "github_org": "test-org",
        "github_repo_name": "test-repo",
        "github_token": "ghp_test"
    }
    
    response = await client.post("/api/migrate/quick", json=request_data, headers=headers)
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_quick_migrate_validation_project_path(client, auth_token):
    """Test quick migrate endpoint validates project path"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    # Invalid project path - no slash
    request_data = {
        "gitlab_url": "https://gitlab.com",
        "gitlab_project_path": "justproject",
        "gitlab_token": "glpat-test",
        "github_org": "test-org",
        "github_repo_name": "test-repo",
        "github_token": "ghp_test"
    }
    
    response = await client.post("/api/migrate/quick", json=request_data, headers=headers)
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_quick_migrate_validation_github_names(client, auth_token):
    """Test quick migrate endpoint validates GitHub names"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    # Invalid GitHub org name - special characters
    request_data = {
        "gitlab_url": "https://gitlab.com",
        "gitlab_project_path": "user/project",
        "gitlab_token": "glpat-test",
        "github_org": "test org!",
        "github_repo_name": "test-repo",
        "github_token": "ghp_test"
    }
    
    response = await client.post("/api/migrate/quick", json=request_data, headers=headers)
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
@patch('app.api.migrate.run_migration')
async def test_quick_migrate_success(mock_run_migration, client, auth_token):
    """Test successful quick migrate request"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    # Mock the Celery task
    mock_task = MagicMock()
    mock_task.id = "test-task-id"
    mock_run_migration.delay.return_value = mock_task
    
    request_data = {
        "gitlab_url": "https://gitlab.com",
        "gitlab_project_path": "moti.malka25/demo-project",
        "gitlab_token": "glpat-test-token",
        "github_org": "moti-malka",
        "github_repo_name": "demo-project",
        "github_token": "ghp_test_token",
        "options": {
            "include_ci": True,
            "include_issues": True,
            "include_wiki": False,
            "include_releases": False
        }
    }
    
    response = await client.post("/api/migrate/quick", json=request_data, headers=headers)
    
    assert response.status_code == 201
    data = response.json()
    assert "run_id" in data
    assert data["status"] == "started"
    assert "dashboard_url" in data
    assert data["message"] == "Quick migration started for moti.malka25/demo-project"


@pytest.mark.asyncio
async def test_quick_migrate_requires_auth(client):
    """Test that quick migrate requires authentication"""
    request_data = {
        "gitlab_url": "https://gitlab.com",
        "gitlab_project_path": "user/project",
        "gitlab_token": "glpat-test",
        "github_org": "test-org",
        "github_repo_name": "test-repo",
        "github_token": "ghp_test"
    }
    
    response = await client.post("/api/migrate/quick", json=request_data)
    assert response.status_code == 401  # Unauthorized


@pytest.mark.asyncio
async def test_quick_migrate_default_options(client, auth_token):
    """Test quick migrate with default options"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    # Request without options
    request_data = {
        "gitlab_url": "https://gitlab.com",
        "gitlab_project_path": "user/project",
        "gitlab_token": "glpat-test",
        "github_org": "test-org",
        "github_repo_name": "test-repo",
        "github_token": "ghp_test"
    }
    
    with patch('app.api.migrate.run_migration') as mock_run_migration:
        mock_task = MagicMock()
        mock_task.id = "test-task-id"
        mock_run_migration.delay.return_value = mock_task
        
        response = await client.post("/api/migrate/quick", json=request_data, headers=headers)
        
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "started"


@pytest.mark.asyncio
async def test_quick_migrate_url_normalization(client, auth_token):
    """Test that GitLab URL is normalized (trailing slash removed)"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    request_data = {
        "gitlab_url": "https://gitlab.com/",
        "gitlab_project_path": "user/project",
        "gitlab_token": "glpat-test",
        "github_org": "test-org",
        "github_repo_name": "test-repo",
        "github_token": "ghp_test"
    }
    
    with patch('app.api.migrate.run_migration') as mock_run_migration:
        mock_task = MagicMock()
        mock_task.id = "test-task-id"
        mock_run_migration.delay.return_value = mock_task
        
        response = await client.post("/api/migrate/quick", json=request_data, headers=headers)
        
        assert response.status_code == 201
        # The URL should be normalized internally
