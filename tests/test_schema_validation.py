"""
Tests for schema validation.
"""

import pytest
from discovery_agent.schema import (
    validate_inventory,
    get_schema,
    InventoryBuilder,
    INVENTORY_SCHEMA,
)


class TestValidateInventory:
    """Tests for inventory validation."""
    
    def test_valid_minimal_inventory(self):
        """Test validation of minimal valid inventory."""
        inventory = {
            "run": {
                "started_at": "2024-01-15T10:00:00+00:00",
                "finished_at": "2024-01-15T10:05:00+00:00",
                "base_url": "https://gitlab.example.com",
                "root_group": "myorg",
                "stats": {
                    "groups": 0,
                    "projects": 0,
                    "errors": 0,
                    "api_calls": 10,
                },
            },
            "groups": [],
            "projects": [],
        }
        
        is_valid, errors = validate_inventory(inventory)
        
        assert is_valid is True
        assert errors == []
    
    def test_valid_full_inventory(self):
        """Test validation of complete inventory."""
        inventory = {
            "run": {
                "started_at": "2024-01-15T10:00:00+00:00",
                "finished_at": "2024-01-15T10:05:00+00:00",
                "base_url": "https://gitlab.example.com",
                "root_group": "myorg",
                "stats": {
                    "groups": 2,
                    "projects": 3,
                    "errors": 1,
                    "api_calls": 150,
                },
            },
            "groups": [
                {
                    "id": 100,
                    "full_path": "myorg",
                    "projects": [1, 2],
                },
                {
                    "id": 101,
                    "full_path": "myorg/subgroup",
                    "projects": [3],
                },
            ],
            "projects": [
                {
                    "id": 1,
                    "path_with_namespace": "myorg/project1",
                    "default_branch": "main",
                    "archived": False,
                    "visibility": "private",
                    "facts": {
                        "has_ci": True,
                        "has_lfs": False,
                        "mr_counts": {"open": 5, "merged": 100, "closed": 10, "total": 115},
                        "issue_counts": {"open": 20, "closed": 80, "total": 100},
                    },
                    "readiness": {
                        "complexity": "medium",
                        "blockers": ["Has GitLab CI/CD pipeline - requires conversion"],
                        "notes": ["Consider renaming default branch from 'master' to 'main'"],
                    },
                    "errors": [],
                },
                {
                    "id": 2,
                    "path_with_namespace": "myorg/project2",
                    "default_branch": None,
                    "archived": True,
                    "visibility": "public",
                    "facts": {
                        "has_ci": False,
                        "has_lfs": "unknown",
                        "mr_counts": "unknown",
                        "issue_counts": "unknown",
                    },
                    "readiness": {
                        "complexity": "low",
                        "blockers": [],
                        "notes": ["Project is archived"],
                    },
                    "errors": [
                        {"step": "detect_lfs", "status": 403, "message": "Permission denied"},
                    ],
                },
                {
                    "id": 3,
                    "path_with_namespace": "myorg/subgroup/project3",
                    "default_branch": "develop",
                    "archived": False,
                    "visibility": "internal",
                    "facts": {
                        "has_ci": "unknown",
                        "has_lfs": True,
                        "mr_counts": {"open": 0, "merged": 0, "closed": 0, "total": 0},
                        "issue_counts": {"open": 0, "closed": 0, "total": 0},
                    },
                    "readiness": {
                        "complexity": "high",
                        "blockers": ["Uses Git LFS - requires LFS migration setup"],
                        "notes": [],
                    },
                    "errors": [],
                },
            ],
        }
        
        is_valid, errors = validate_inventory(inventory)
        
        assert is_valid is True
        assert errors == []
    
    def test_invalid_missing_run(self):
        """Test validation fails when run is missing."""
        inventory = {
            "groups": [],
            "projects": [],
        }
        
        is_valid, errors = validate_inventory(inventory)
        
        assert is_valid is False
        assert len(errors) > 0
        assert any("run" in e for e in errors)
    
    def test_invalid_missing_stats(self):
        """Test validation fails when stats is missing."""
        inventory = {
            "run": {
                "started_at": "2024-01-15T10:00:00+00:00",
                "finished_at": "2024-01-15T10:05:00+00:00",
                "base_url": "https://gitlab.example.com",
                "root_group": "myorg",
                # stats is missing
            },
            "groups": [],
            "projects": [],
        }
        
        is_valid, errors = validate_inventory(inventory)
        
        assert is_valid is False
        assert any("stats" in e for e in errors)
    
    def test_invalid_visibility_value(self):
        """Test validation fails with invalid visibility."""
        inventory = {
            "run": {
                "started_at": "2024-01-15T10:00:00+00:00",
                "finished_at": "2024-01-15T10:05:00+00:00",
                "base_url": "https://gitlab.example.com",
                "root_group": "myorg",
                "stats": {"groups": 0, "projects": 1, "errors": 0, "api_calls": 10},
            },
            "groups": [],
            "projects": [
                {
                    "id": 1,
                    "path_with_namespace": "myorg/project1",
                    "default_branch": "main",
                    "archived": False,
                    "visibility": "secret",  # Invalid value
                    "facts": {
                        "has_ci": False,
                        "has_lfs": False,
                        "mr_counts": {"open": 0, "merged": 0, "closed": 0, "total": 0},
                        "issue_counts": {"open": 0, "closed": 0, "total": 0},
                    },
                    "readiness": {
                        "complexity": "low",
                        "blockers": [],
                        "notes": [],
                    },
                    "errors": [],
                },
            ],
        }
        
        is_valid, errors = validate_inventory(inventory)
        
        assert is_valid is False
        assert any("visibility" in e for e in errors)
    
    def test_invalid_complexity_value(self):
        """Test validation fails with invalid complexity."""
        inventory = {
            "run": {
                "started_at": "2024-01-15T10:00:00+00:00",
                "finished_at": "2024-01-15T10:05:00+00:00",
                "base_url": "https://gitlab.example.com",
                "root_group": "myorg",
                "stats": {"groups": 0, "projects": 1, "errors": 0, "api_calls": 10},
            },
            "groups": [],
            "projects": [
                {
                    "id": 1,
                    "path_with_namespace": "myorg/project1",
                    "default_branch": "main",
                    "archived": False,
                    "visibility": "private",
                    "facts": {
                        "has_ci": False,
                        "has_lfs": False,
                        "mr_counts": {"open": 0, "merged": 0, "closed": 0, "total": 0},
                        "issue_counts": {"open": 0, "closed": 0, "total": 0},
                    },
                    "readiness": {
                        "complexity": "extreme",  # Invalid value
                        "blockers": [],
                        "notes": [],
                    },
                    "errors": [],
                },
            ],
        }
        
        is_valid, errors = validate_inventory(inventory)
        
        assert is_valid is False
        assert any("complexity" in e for e in errors)
    
    def test_valid_unknown_facts(self):
        """Test that 'unknown' string is valid for facts."""
        inventory = {
            "run": {
                "started_at": "2024-01-15T10:00:00+00:00",
                "finished_at": "2024-01-15T10:05:00+00:00",
                "base_url": "https://gitlab.example.com",
                "root_group": "myorg",
                "stats": {"groups": 0, "projects": 1, "errors": 0, "api_calls": 10},
            },
            "groups": [],
            "projects": [
                {
                    "id": 1,
                    "path_with_namespace": "myorg/project1",
                    "default_branch": "main",
                    "archived": False,
                    "visibility": "private",
                    "facts": {
                        "has_ci": "unknown",
                        "has_lfs": "unknown",
                        "mr_counts": "unknown",
                        "issue_counts": "unknown",
                    },
                    "readiness": {
                        "complexity": "medium",
                        "blockers": [],
                        "notes": [],
                    },
                    "errors": [],
                },
            ],
        }
        
        is_valid, errors = validate_inventory(inventory)
        
        assert is_valid is True
        assert errors == []


class TestGetSchema:
    """Tests for get_schema function."""
    
    def test_returns_schema(self):
        """Test that get_schema returns the schema dict."""
        schema = get_schema()
        
        assert isinstance(schema, dict)
        assert "$schema" in schema
        assert schema["type"] == "object"
        assert "properties" in schema
    
    def test_schema_is_same_as_constant(self):
        """Test that get_schema returns the same schema as INVENTORY_SCHEMA."""
        schema = get_schema()
        
        assert schema is INVENTORY_SCHEMA


class TestInventoryBuilder:
    """Tests for InventoryBuilder class."""
    
    def test_add_group(self):
        """Test adding a group."""
        builder = InventoryBuilder()
        
        builder.add_group(100, "myorg")
        
        assert len(builder.groups) == 1
        assert builder.groups[0]["id"] == 100
        assert builder.groups[0]["full_path"] == "myorg"
        assert builder.groups[0]["projects"] == []
    
    def test_add_group_no_duplicates(self):
        """Test that duplicate groups are not added."""
        builder = InventoryBuilder()
        
        builder.add_group(100, "myorg")
        builder.add_group(100, "myorg")
        
        assert len(builder.groups) == 1
    
    def test_add_project_to_group(self):
        """Test associating project with group."""
        builder = InventoryBuilder()
        
        builder.add_group(100, "myorg")
        builder.add_project_to_group(100, 1)
        builder.add_project_to_group(100, 2)
        
        assert builder.groups[0]["projects"] == [1, 2]
    
    def test_add_project_to_group_no_duplicates(self):
        """Test that duplicate project associations are not added."""
        builder = InventoryBuilder()
        
        builder.add_group(100, "myorg")
        builder.add_project_to_group(100, 1)
        builder.add_project_to_group(100, 1)
        
        assert builder.groups[0]["projects"] == [1]
    
    def test_add_project(self):
        """Test adding a project."""
        builder = InventoryBuilder()
        
        builder.add_project(
            project_id=1,
            path_with_namespace="myorg/project1",
            default_branch="main",
            archived=False,
            visibility="private",
        )
        
        assert len(builder.projects) == 1
        project = builder.projects[0]
        assert project["id"] == 1
        assert project["path_with_namespace"] == "myorg/project1"
        assert project["default_branch"] == "main"
        assert project["archived"] is False
        assert project["visibility"] == "private"
        # Check defaults
        assert project["facts"]["has_ci"] == "unknown"
        assert project["readiness"]["complexity"] == "medium"
        assert project["errors"] == []
    
    def test_add_project_with_custom_facts(self):
        """Test adding a project with custom facts."""
        builder = InventoryBuilder()
        
        builder.add_project(
            project_id=1,
            path_with_namespace="myorg/project1",
            default_branch="main",
            archived=False,
            visibility="private",
            facts={
                "has_ci": True,
                "has_lfs": False,
                "mr_counts": {"open": 5, "merged": 10, "closed": 2, "total": 17},
                "issue_counts": {"open": 3, "closed": 7, "total": 10},
            },
        )
        
        project = builder.projects[0]
        assert project["facts"]["has_ci"] is True
        assert project["facts"]["has_lfs"] is False
        assert project["facts"]["mr_counts"]["total"] == 17
    
    def test_update_project_facts(self):
        """Test updating project facts."""
        builder = InventoryBuilder()
        
        builder.add_project(
            project_id=1,
            path_with_namespace="myorg/project1",
            default_branch="main",
            archived=False,
            visibility="private",
        )
        
        builder.update_project_facts(1, {"has_ci": True})
        
        assert builder.projects[0]["facts"]["has_ci"] is True
    
    def test_add_project_error(self):
        """Test adding an error to a project."""
        builder = InventoryBuilder()
        
        builder.add_project(
            project_id=1,
            path_with_namespace="myorg/project1",
            default_branch="main",
            archived=False,
            visibility="private",
        )
        
        builder.add_project_error(1, "detect_ci", "Permission denied", 403)
        
        errors = builder.projects[0]["errors"]
        assert len(errors) == 1
        assert errors[0]["step"] == "detect_ci"
        assert errors[0]["status"] == 403
        assert errors[0]["message"] == "Permission denied"
    
    def test_build_sorts_output(self):
        """Test that build sorts groups and projects."""
        builder = InventoryBuilder()
        
        # Add in non-sorted order
        builder.add_group(102, "myorg/z-group")
        builder.add_group(101, "myorg/a-group")
        builder.add_group(100, "myorg")
        
        builder.add_project(3, "myorg/z-project", "main", False, "private")
        builder.add_project(1, "myorg/a-project", "main", False, "private")
        builder.add_project(2, "myorg/m-project", "main", False, "private")
        
        inventory = builder.build(
            started_at="2024-01-15T10:00:00+00:00",
            finished_at="2024-01-15T10:05:00+00:00",
            base_url="https://gitlab.example.com",
            root_group="myorg",
            api_calls=50,
        )
        
        # Groups should be sorted by full_path
        assert inventory["groups"][0]["full_path"] == "myorg"
        assert inventory["groups"][1]["full_path"] == "myorg/a-group"
        assert inventory["groups"][2]["full_path"] == "myorg/z-group"
        
        # Projects should be sorted by path_with_namespace
        assert inventory["projects"][0]["path_with_namespace"] == "myorg/a-project"
        assert inventory["projects"][1]["path_with_namespace"] == "myorg/m-project"
        assert inventory["projects"][2]["path_with_namespace"] == "myorg/z-project"
    
    def test_build_counts_errors(self):
        """Test that build correctly counts errors."""
        builder = InventoryBuilder()
        
        builder.add_project(1, "myorg/project1", "main", False, "private")
        builder.add_project(2, "myorg/project2", "main", False, "private")
        
        builder.add_project_error(1, "step1", "error1", 403)
        builder.add_project_error(1, "step2", "error2", 500)
        builder.add_project_error(2, "step1", "error3", 404)
        
        inventory = builder.build(
            started_at="2024-01-15T10:00:00+00:00",
            finished_at="2024-01-15T10:05:00+00:00",
            base_url="https://gitlab.example.com",
            root_group="myorg",
            api_calls=50,
        )
        
        assert inventory["run"]["stats"]["errors"] == 3
    
    def test_build_produces_valid_inventory(self):
        """Test that build produces a valid inventory."""
        builder = InventoryBuilder()
        
        builder.add_group(100, "myorg")
        builder.add_project_to_group(100, 1)
        
        builder.add_project(
            project_id=1,
            path_with_namespace="myorg/project1",
            default_branch="main",
            archived=False,
            visibility="private",
            facts={
                "has_ci": True,
                "has_lfs": False,
                "mr_counts": {"open": 0, "merged": 0, "closed": 0, "total": 0},
                "issue_counts": {"open": 0, "closed": 0, "total": 0},
            },
            readiness={
                "complexity": "low",
                "blockers": [],
                "notes": [],
            },
        )
        
        inventory = builder.build(
            started_at="2024-01-15T10:00:00+00:00",
            finished_at="2024-01-15T10:05:00+00:00",
            base_url="https://gitlab.example.com",
            root_group="myorg",
            api_calls=50,
        )
        
        is_valid, errors = validate_inventory(inventory)
        
        assert is_valid is True
        assert errors == []
