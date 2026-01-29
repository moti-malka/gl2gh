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
