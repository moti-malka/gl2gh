"""Tests for token masking in API responses"""

import pytest
from httpx import AsyncClient
from app.main import app
from app.db import connect_to_mongo, close_mongo_connection
from app.utils.security import sanitize_project_settings, get_token_last4


@pytest.fixture(scope="module")
async def client():
    """Create test client"""
    await connect_to_mongo()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    await close_mongo_connection()


def test_sanitize_project_settings_with_gitlab_token():
    """Test that GitLab tokens are properly masked"""
    settings = {
        "gitlab": {
            "url": "https://gitlab.com",
            "token": "glpat-abcdefghijklmnopqrst"
        },
        "github": {
            "org": "myorg"
        }
    }
    
    sanitized = sanitize_project_settings(settings)
    
    # Check GitLab token is masked
    assert "token" not in sanitized["gitlab"]
    assert "token_last4" in sanitized["gitlab"]
    assert sanitized["gitlab"]["token_last4"] == "qrst"
    assert sanitized["gitlab"]["url"] == "https://gitlab.com"
    
    # Check GitHub settings are preserved
    assert sanitized["github"]["org"] == "myorg"


def test_sanitize_project_settings_with_github_token():
    """Test that GitHub tokens are properly masked"""
    settings = {
        "gitlab": {
            "url": "https://gitlab.com"
        },
        "github": {
            "org": "myorg",
            "token": "ghp_1234567890abcdefghij1234567890abcd"
        }
    }
    
    sanitized = sanitize_project_settings(settings)
    
    # Check GitHub token is masked
    assert "token" not in sanitized["github"]
    assert "token_last4" in sanitized["github"]
    assert sanitized["github"]["token_last4"] == "abcd"
    assert sanitized["github"]["org"] == "myorg"


def test_sanitize_project_settings_with_both_tokens():
    """Test that both GitLab and GitHub tokens are masked"""
    settings = {
        "gitlab": {
            "url": "https://gitlab.com",
            "token": "glpat-secrettoken123"
        },
        "github": {
            "org": "myorg",
            "token": "ghp_anothersecrettoken456"
        },
        "budgets": {
            "max_api_calls": 5000
        }
    }
    
    sanitized = sanitize_project_settings(settings)
    
    # Check GitLab token is masked
    assert "token" not in sanitized["gitlab"]
    assert sanitized["gitlab"]["token_last4"] == "n123"
    
    # Check GitHub token is masked
    assert "token" not in sanitized["github"]
    assert sanitized["github"]["token_last4"] == "n456"
    
    # Check other settings are preserved
    assert sanitized["budgets"]["max_api_calls"] == 5000


def test_sanitize_project_settings_with_no_tokens():
    """Test that settings without tokens are preserved"""
    settings = {
        "gitlab": {
            "url": "https://gitlab.com"
        },
        "github": {
            "org": "myorg"
        },
        "budgets": {
            "max_api_calls": 5000
        }
    }
    
    sanitized = sanitize_project_settings(settings)
    
    # Check all settings are preserved
    assert sanitized["gitlab"]["url"] == "https://gitlab.com"
    assert sanitized["github"]["org"] == "myorg"
    assert sanitized["budgets"]["max_api_calls"] == 5000
    
    # Check no token_last4 fields were added
    assert "token_last4" not in sanitized["gitlab"]
    assert "token_last4" not in sanitized["github"]


def test_get_token_last4():
    """Test get_token_last4 utility function"""
    assert get_token_last4("glpat-abcdefgh") == "efgh"
    assert get_token_last4("1234567890") == "7890"
    assert get_token_last4("abc") == "***"
    assert get_token_last4("") == "***"


@pytest.mark.asyncio
async def test_api_project_masks_tokens(client):
    """Test that project API endpoint properly masks tokens"""
    # Register and login
    register_data = {
        "username": "tokentest",
        "email": "tokentest@example.com",
        "password": "testpass123"
    }
    await client.post("/api/auth/register", json=register_data)
    
    login_data = {
        "username": "tokentest",
        "password": "testpass123"
    }
    response = await client.post("/api/auth/login", json=login_data)
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create project with tokens in settings
    project_data = {
        "name": "Token Masking Test",
        "description": "Test token masking",
        "settings": {
            "gitlab": {
                "url": "https://gitlab.com",
                "token": "glpat-verysecrettoken123"
            },
            "github": {
                "org": "testorg",
                "token": "ghp_anothersecrettoken456"
            }
        }
    }
    
    response = await client.post("/api/projects", json=project_data, headers=headers)
    assert response.status_code == 201
    project = response.json()
    project_id = project["id"]
    
    # Verify tokens are masked in create response
    assert "token" not in project["settings"]["gitlab"]
    assert project["settings"]["gitlab"]["token_last4"] == "n123"
    assert "token" not in project["settings"]["github"]
    assert project["settings"]["github"]["token_last4"] == "n456"
    
    # Verify tokens are masked when fetching project
    response = await client.get(f"/api/projects/{project_id}", headers=headers)
    assert response.status_code == 200
    fetched_project = response.json()
    
    assert "token" not in fetched_project["settings"]["gitlab"]
    assert fetched_project["settings"]["gitlab"]["token_last4"] == "n123"
    assert "token" not in fetched_project["settings"]["github"]
    assert fetched_project["settings"]["github"]["token_last4"] == "n456"
    
    # Verify tokens are masked in list response
    response = await client.get("/api/projects", headers=headers)
    assert response.status_code == 200
    projects = response.json()
    
    # Find our project in the list
    test_project = next((p for p in projects if p["id"] == project_id), None)
    assert test_project is not None
    assert "token" not in test_project["settings"]["gitlab"]
    assert test_project["settings"]["gitlab"]["token_last4"] == "n123"
    assert "token" not in test_project["settings"]["github"]
    assert test_project["settings"]["github"]["token_last4"] == "n456"
