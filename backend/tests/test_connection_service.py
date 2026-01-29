"""Tests for ConnectionService"""

import pytest


@pytest.mark.asyncio
async def test_store_gitlab_connection(connection_service, test_project):
    """Test storing GitLab connection"""
    conn = await connection_service.store_gitlab_connection(
        project_id=str(test_project.id),
        token="glpat-test-token-12345678",
        base_url="https://gitlab.example.com"
    )
    
    assert conn.type == "gitlab"
    assert conn.base_url == "https://gitlab.example.com"
    assert conn.token_last4 == "5678"
    assert str(conn.project_id) == str(test_project.id)


@pytest.mark.asyncio
async def test_store_github_connection(connection_service, test_project):
    """Test storing GitHub connection"""
    conn = await connection_service.store_github_connection(
        project_id=str(test_project.id),
        token="ghp_test1234567890123456789012345678",
        base_url="https://api.github.com"
    )
    
    assert conn.type == "github"
    assert conn.base_url == "https://api.github.com"
    assert conn.token_last4 == "5678"


@pytest.mark.asyncio
async def test_get_connections(connection_service, test_project):
    """Test getting all connections for a project"""
    # Store connections
    await connection_service.store_gitlab_connection(
        project_id=str(test_project.id),
        token="glpat-test-token"
    )
    await connection_service.store_github_connection(
        project_id=str(test_project.id),
        token="ghp_test_token"
    )
    
    # Get connections
    connections = await connection_service.get_connections(str(test_project.id))
    assert len(connections) == 2
    
    types = {c.type for c in connections}
    assert "gitlab" in types
    assert "github" in types


@pytest.mark.asyncio
async def test_get_connection_by_type(connection_service, test_project):
    """Test getting connection by type"""
    await connection_service.store_gitlab_connection(
        project_id=str(test_project.id),
        token="glpat-test-token"
    )
    
    conn = await connection_service.get_connection_by_type(
        str(test_project.id),
        "gitlab"
    )
    
    assert conn is not None
    assert conn.type == "gitlab"


@pytest.mark.asyncio
async def test_get_decrypted_token(connection_service, test_project):
    """Test getting decrypted token"""
    original_token = "glpat-test-secret-token"
    conn = await connection_service.store_gitlab_connection(
        project_id=str(test_project.id),
        token=original_token
    )
    
    decrypted = await connection_service.get_decrypted_token(str(conn.id))
    assert decrypted == original_token


@pytest.mark.asyncio
async def test_delete_connection(connection_service, test_project):
    """Test deleting connection"""
    conn = await connection_service.store_gitlab_connection(
        project_id=str(test_project.id),
        token="glpat-test-token"
    )
    
    success = await connection_service.delete_connection(str(conn.id))
    assert success is True
    
    # Verify connection is deleted
    connections = await connection_service.get_connections(str(test_project.id))
    assert len(connections) == 0


@pytest.mark.asyncio
async def test_replace_existing_connection(connection_service, test_project):
    """Test that storing a new connection replaces existing one of same type"""
    # Store first connection
    conn1 = await connection_service.store_gitlab_connection(
        project_id=str(test_project.id),
        token="glpat-first-token"
    )
    
    # Store second connection (should replace first)
    conn2 = await connection_service.store_gitlab_connection(
        project_id=str(test_project.id),
        token="glpat-second-token"
    )
    
    # Should only have one GitLab connection
    connections = await connection_service.get_connections(str(test_project.id))
    gitlab_conns = [c for c in connections if c.type == "gitlab"]
    
    assert len(gitlab_conns) == 1
    assert str(gitlab_conns[0].id) == str(conn2.id)


@pytest.mark.asyncio
async def test_get_connections_from_project_settings(connection_service, project_service, test_user):
    """Test that get_connections returns connections from project settings"""
    # Create a project with credentials in settings
    project = await project_service.create_project(
        name="Test Project with Settings",
        created_by=str(test_user.id),
        settings={
            "gitlab": {
                "url": "https://gitlab.com",
                "token": "glpat-from-settings-1234"
            },
            "github": {
                "token": "ghp_from_settings_5678",
                "org": "test-org"
            }
        }
    )
    
    # Get connections - should return connections from settings
    connections = await connection_service.get_connections(str(project.id))
    
    assert len(connections) == 2
    
    # Check GitLab connection
    gitlab_conn = next((c for c in connections if c.type == "gitlab"), None)
    assert gitlab_conn is not None
    assert gitlab_conn.base_url == "https://gitlab.com"
    assert gitlab_conn.token_last4 == "1234"
    
    # Check GitHub connection
    github_conn = next((c for c in connections if c.type == "github"), None)
    assert github_conn is not None
    assert github_conn.token_last4 == "5678"


@pytest.mark.asyncio
async def test_get_connections_prioritizes_connections_collection(connection_service, project_service, test_user):
    """Test that connections collection takes priority over project settings"""
    # Create a project with credentials in settings
    project = await project_service.create_project(
        name="Test Project with Settings",
        created_by=str(test_user.id),
        settings={
            "gitlab": {
                "url": "https://gitlab.com",
                "token": "glpat-from-settings-1234"
            }
        }
    )
    
    # Store a connection in connections collection (should override settings)
    await connection_service.store_gitlab_connection(
        project_id=str(project.id),
        token="glpat-from-collection-5678",
        base_url="https://gitlab.example.com"
    )
    
    # Get connections - should return connection from collection, not settings
    connections = await connection_service.get_connections(str(project.id))
    
    assert len(connections) == 1
    gitlab_conn = connections[0]
    assert gitlab_conn.type == "gitlab"
    assert gitlab_conn.base_url == "https://gitlab.example.com"
    assert gitlab_conn.token_last4 == "5678"


@pytest.mark.asyncio
async def test_get_connection_by_type_from_settings(connection_service, project_service, test_user):
    """Test that get_connection_by_type returns connection from project settings"""
    # Create a project with credentials in settings
    project = await project_service.create_project(
        name="Test Project with Settings",
        created_by=str(test_user.id),
        settings={
            "gitlab": {
                "url": "https://gitlab.com",
                "token": "glpat-from-settings-1234"
            }
        }
    )
    
    # Get GitLab connection by type - should return from settings
    gitlab_conn = await connection_service.get_connection_by_type(
        str(project.id),
        "gitlab"
    )
    
    assert gitlab_conn is not None
    assert gitlab_conn.type == "gitlab"
    assert gitlab_conn.base_url == "https://gitlab.com"
    assert gitlab_conn.token_last4 == "1234"
    
    # GitHub connection should be None (not in settings)
    github_conn = await connection_service.get_connection_by_type(
        str(project.id),
        "github"
    )
    
    assert github_conn is None


@pytest.mark.asyncio
async def test_get_connections_empty_when_no_credentials(connection_service, test_project):
    """Test that get_connections returns empty list when project has no credentials"""
    connections = await connection_service.get_connections(str(test_project.id))
    assert len(connections) == 0
