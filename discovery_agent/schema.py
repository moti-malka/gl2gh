"""
JSON Schema definitions for discovery output validation.

Defines the structure of the inventory.json output file.
"""

from __future__ import annotations

from typing import Any

import jsonschema
from jsonschema import Draft7Validator, ValidationError

# JSON Schema for the final inventory output
INVENTORY_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "GitLab Discovery Inventory",
    "description": "Inventory and readiness report for GitLab to GitHub migration",
    "type": "object",
    "required": ["run", "groups", "projects"],
    "additionalProperties": False,
    "properties": {
        "run": {
            "type": "object",
            "description": "Metadata about the discovery run",
            "required": ["started_at", "finished_at", "base_url", "root_group", "stats"],
            "additionalProperties": False,
            "properties": {
                "started_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "ISO8601 timestamp when discovery started",
                },
                "finished_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "ISO8601 timestamp when discovery finished",
                },
                "base_url": {
                    "type": "string",
                    "description": "GitLab instance base URL",
                },
                "root_group": {
                    "type": "string",
                    "description": "Root group path that was scanned",
                },
                "stats": {
                    "type": "object",
                    "description": "Summary statistics",
                    "required": ["groups", "projects", "errors", "api_calls"],
                    "additionalProperties": False,
                    "properties": {
                        "groups": {
                            "type": "integer",
                            "minimum": 0,
                            "description": "Number of groups discovered",
                        },
                        "projects": {
                            "type": "integer",
                            "minimum": 0,
                            "description": "Number of projects discovered",
                        },
                        "errors": {
                            "type": "integer",
                            "minimum": 0,
                            "description": "Number of errors encountered",
                        },
                        "api_calls": {
                            "type": "integer",
                            "minimum": 0,
                            "description": "Total API calls made",
                        },
                    },
                },
            },
        },
        "groups": {
            "type": "array",
            "description": "List of discovered groups",
            "items": {
                "type": "object",
                "required": ["id", "full_path", "projects"],
                "additionalProperties": False,
                "properties": {
                    "id": {
                        "type": "integer",
                        "description": "GitLab group ID",
                    },
                    "full_path": {
                        "type": "string",
                        "description": "Full path of the group",
                    },
                    "projects": {
                        "type": "array",
                        "description": "List of project IDs in this group",
                        "items": {
                            "type": "integer",
                        },
                    },
                },
            },
        },
        "projects": {
            "type": "array",
            "description": "List of discovered projects with details",
            "items": {
                "type": "object",
                "required": [
                    "id",
                    "path_with_namespace",
                    "default_branch",
                    "archived",
                    "visibility",
                    "facts",
                    "readiness",
                    "errors",
                ],
                "additionalProperties": True,
                "properties": {
                    "id": {
                        "type": "integer",
                        "description": "GitLab project ID",
                    },
                    "path_with_namespace": {
                        "type": "string",
                        "description": "Full path including namespace",
                    },
                    "default_branch": {
                        "type": ["string", "null"],
                        "description": "Default branch name",
                    },
                    "archived": {
                        "type": "boolean",
                        "description": "Whether project is archived",
                    },
                    "visibility": {
                        "type": "string",
                        "enum": ["private", "internal", "public"],
                        "description": "Project visibility level",
                    },
                    "facts": {
                        "type": "object",
                        "description": "Discovered facts about the project",
                        "required": ["has_ci", "has_lfs", "mr_counts", "issue_counts"],
                        "additionalProperties": True,
                        "properties": {
                            "has_ci": {
                                "oneOf": [
                                    {"type": "boolean"},
                                    {"type": "string", "const": "unknown"},
                                ],
                                "description": "Whether project has CI configuration",
                            },
                            "has_lfs": {
                                "oneOf": [
                                    {"type": "boolean"},
                                    {"type": "string", "const": "unknown"},
                                ],
                                "description": "Whether project uses Git LFS",
                            },
                            "mr_counts": {
                                "oneOf": [
                                    {
                                        "type": "object",
                                        "required": ["open", "merged", "closed", "total"],
                                        "additionalProperties": True,
                                        "properties": {
                                            "open": {
                                                "oneOf": [
                                                    {"type": "integer", "minimum": 0},
                                                    {"type": "string"},
                                                ],
                                            },
                                            "merged": {
                                                "oneOf": [
                                                    {"type": "integer", "minimum": 0},
                                                    {"type": "string"},
                                                ],
                                            },
                                            "closed": {
                                                "oneOf": [
                                                    {"type": "integer", "minimum": 0},
                                                    {"type": "string"},
                                                ],
                                            },
                                            "total": {
                                                "oneOf": [
                                                    {"type": "integer", "minimum": 0},
                                                    {"type": "string"},
                                                ],
                                            },
                                        },
                                    },
                                    {"type": "string", "const": "unknown"},
                                ],
                                "description": "Merge request counts by state",
                            },
                            "issue_counts": {
                                "oneOf": [
                                    {
                                        "type": "object",
                                        "required": ["open", "closed", "total"],
                                        "additionalProperties": True,
                                        "properties": {
                                            "open": {
                                                "oneOf": [
                                                    {"type": "integer", "minimum": 0},
                                                    {"type": "string"},
                                                ],
                                            },
                                            "closed": {
                                                "oneOf": [
                                                    {"type": "integer", "minimum": 0},
                                                    {"type": "string"},
                                                ],
                                            },
                                            "total": {
                                                "oneOf": [
                                                    {"type": "integer", "minimum": 0},
                                                    {"type": "string"},
                                                ],
                                            },
                                        },
                                    },
                                    {"type": "string", "const": "unknown"},
                                ],
                                "description": "Issue counts by state",
                            },
                            "repo_profile": {
                                "type": "object",
                                "description": "Repository profile metrics (deep mode only)",
                                "additionalProperties": False,
                                "properties": {
                                    "branches_count": {
                                        "oneOf": [
                                            {"type": "integer", "minimum": 0},
                                            {"type": "string"},
                                        ],
                                        "description": "Number of branches",
                                    },
                                    "tags_count": {
                                        "oneOf": [
                                            {"type": "integer", "minimum": 0},
                                            {"type": "string"},
                                        ],
                                        "description": "Number of tags",
                                    },
                                    "has_submodules": {
                                        "oneOf": [
                                            {"type": "boolean"},
                                            {"type": "string", "const": "unknown"},
                                        ],
                                        "description": "Whether project uses Git submodules",
                                    },
                                    "has_lfs": {
                                        "oneOf": [
                                            {"type": "boolean"},
                                            {"type": "string", "const": "unknown"},
                                        ],
                                        "description": "Whether project uses Git LFS",
                                    },
                                },
                            },
                            "ci_profile": {
                                "type": "object",
                                "description": "CI/CD profile analysis (deep mode only)",
                                "additionalProperties": True,
                                "properties": {
                                    "present": {
                                        "type": "boolean",
                                        "description": "Whether CI configuration exists",
                                    },
                                    "total_lines": {
                                        "type": "integer",
                                        "minimum": 0,
                                        "description": "Total lines in CI file",
                                    },
                                    "features": {
                                        "type": "object",
                                        "description": "CI features detected",
                                        "additionalProperties": {"type": "boolean"},
                                    },
                                    "runner_hints": {
                                        "type": "object",
                                        "description": "Runner configuration hints",
                                        "additionalProperties": {"type": "boolean"},
                                    },
                                },
                            },
                            "migration_estimate": {
                                "type": "object",
                                "description": "Migration effort estimate (deep mode only)",
                                "additionalProperties": False,
                                "properties": {
                                    "work_score": {
                                        "type": "integer",
                                        "minimum": 0,
                                        "maximum": 100,
                                        "description": "Overall work score (0-100)",
                                    },
                                    "bucket": {
                                        "type": "string",
                                        "enum": ["S", "M", "L", "XL"],
                                        "description": "Size bucket for migration effort",
                                    },
                                    "drivers": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Human-readable reasons for score",
                                    },
                                },
                            },
                        },
                    },
                    "readiness": {
                        "type": "object",
                        "description": "Migration readiness assessment",
                        "required": ["complexity", "blockers", "notes"],
                        "additionalProperties": False,
                        "properties": {
                            "complexity": {
                                "type": "string",
                                "enum": ["low", "medium", "high"],
                                "description": "Estimated migration complexity",
                            },
                            "blockers": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Issues that may block migration",
                            },
                            "notes": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Additional notes and observations",
                            },
                        },
                    },
                    "errors": {
                        "type": "array",
                        "description": "Errors encountered during discovery",
                        "items": {
                            "type": "object",
                            "required": ["step", "message"],
                            "additionalProperties": False,
                            "properties": {
                                "step": {
                                    "type": "string",
                                    "description": "Discovery step where error occurred",
                                },
                                "status": {
                                    "type": ["integer", "null"],
                                    "description": "HTTP status code if applicable",
                                },
                                "message": {
                                    "type": "string",
                                    "description": "Error message",
                                },
                            },
                        },
                    },
                },
            },
        },
    },
}


def validate_inventory(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validate inventory data against the schema.
    
    Args:
        data: Inventory data dictionary
        
    Returns:
        Tuple of (is_valid, list_of_error_messages)
    """
    validator = Draft7Validator(INVENTORY_SCHEMA)
    errors = list(validator.iter_errors(data))
    
    if not errors:
        return True, []
    
    error_messages = []
    for error in errors:
        path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
        error_messages.append(f"{path}: {error.message}")
    
    return False, error_messages


def get_schema() -> dict[str, Any]:
    """Return the inventory JSON schema."""
    return INVENTORY_SCHEMA


class InventoryBuilder:
    """Helper class to build a valid inventory structure."""
    
    def __init__(self):
        self.groups: list[dict[str, Any]] = []
        self.projects: list[dict[str, Any]] = []
        self._group_index: dict[int, dict[str, Any]] = {}
    
    def add_group(self, group_id: int, full_path: str) -> None:
        """Add a group to the inventory."""
        if group_id not in self._group_index:
            group = {
                "id": group_id,
                "full_path": full_path,
                "projects": [],
            }
            self.groups.append(group)
            self._group_index[group_id] = group
    
    def add_project_to_group(self, group_id: int, project_id: int) -> None:
        """Associate a project with a group."""
        if group_id in self._group_index:
            if project_id not in self._group_index[group_id]["projects"]:
                self._group_index[group_id]["projects"].append(project_id)
    
    def add_project(
        self,
        project_id: int,
        path_with_namespace: str,
        default_branch: str | None,
        archived: bool,
        visibility: str,
        facts: dict[str, Any] | None = None,
        readiness: dict[str, Any] | None = None,
        errors: list[dict[str, Any]] | None = None,
        estimate: dict[str, Any] | None = None,
    ) -> None:
        """Add a project to the inventory."""
        project = {
            "id": project_id,
            "path_with_namespace": path_with_namespace,
            "default_branch": default_branch,
            "archived": archived,
            "visibility": visibility,
            "facts": facts or {
                "has_ci": "unknown",
                "has_lfs": "unknown",
                "mr_counts": "unknown",
                "issue_counts": "unknown",
            },
            "readiness": readiness or {
                "complexity": "medium",
                "blockers": [],
                "notes": [],
            },
            "errors": errors or [],
        }
        
        # Add v2 estimate if present
        if estimate:
            project["estimate"] = estimate
        
        self.projects.append(project)
    
    def update_project_facts(self, project_id: int, facts: dict[str, Any]) -> None:
        """Update facts for an existing project."""
        for project in self.projects:
            if project["id"] == project_id:
                project["facts"].update(facts)
                break
    
    def update_project_readiness(self, project_id: int, readiness: dict[str, Any]) -> None:
        """Update readiness for an existing project."""
        for project in self.projects:
            if project["id"] == project_id:
                project["readiness"].update(readiness)
                break
    
    def add_project_error(
        self,
        project_id: int,
        step: str,
        message: str,
        status: int | None = None,
    ) -> None:
        """Add an error to a project."""
        for project in self.projects:
            if project["id"] == project_id:
                project["errors"].append({
                    "step": step,
                    "status": status,
                    "message": message,
                })
                break
    
    def build(
        self,
        started_at: str,
        finished_at: str,
        base_url: str,
        root_group: str,
        api_calls: int,
    ) -> dict[str, Any]:
        """
        Build the final inventory structure.
        
        Returns:
            Complete inventory dictionary ready for serialization
        """
        # Sort groups and projects for deterministic output
        sorted_groups = sorted(self.groups, key=lambda g: g["full_path"])
        sorted_projects = sorted(self.projects, key=lambda p: p["path_with_namespace"])
        
        # Count errors
        total_errors = sum(len(p["errors"]) for p in sorted_projects)
        
        return {
            "run": {
                "started_at": started_at,
                "finished_at": finished_at,
                "base_url": base_url,
                "root_group": root_group,
                "stats": {
                    "groups": len(sorted_groups),
                    "projects": len(sorted_projects),
                    "errors": total_errors,
                    "api_calls": api_calls,
                },
            },
            "groups": sorted_groups,
            "projects": sorted_projects,
        }
