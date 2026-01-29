"""Tests for ProjectService"""

import pytest


@pytest.mark.asyncio
async def test_create_project(project_service, test_user):
    """Test project creation"""
    project = await project_service.create_project(
        name="New Project",
        created_by=str(test_user.id),
        description="A new test project"
    )
    
    assert project.name == "New Project"
    assert project.description == "A new test project"
    assert str(project.created_by) == str(test_user.id)
    assert project.status == "active"
    assert project.id is not None


@pytest.mark.asyncio
async def test_get_project(project_service, test_project):
    """Test getting project by ID"""
    project = await project_service.get_project(str(test_project.id))
    assert project is not None
    assert project.name == test_project.name


@pytest.mark.asyncio
async def test_list_projects(project_service, test_user, test_project):
    """Test listing projects"""
    projects = await project_service.list_projects(
        user_id=str(test_user.id),
        skip=0,
        limit=10
    )
    
    assert len(projects) >= 1
    assert any(str(p.id) == str(test_project.id) for p in projects)


@pytest.mark.asyncio
async def test_update_project(project_service, test_project):
    """Test updating project"""
    updated = await project_service.update_project(
        str(test_project.id),
        {"description": "Updated description"}
    )
    
    assert updated is not None
    assert updated.description == "Updated description"


@pytest.mark.asyncio
async def test_delete_project(project_service, test_project):
    """Test soft deleting project"""
    success = await project_service.delete_project(str(test_project.id))
    assert success is True
    
    # Verify project is archived
    project = await project_service.get_project(str(test_project.id))
    assert project is not None
    assert project.status == "archived"
