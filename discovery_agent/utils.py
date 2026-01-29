"""
Utility functions for the Discovery Agent.

Common helpers for time, logging, and data manipulation.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def setup_logging(
    level: int = logging.INFO,
    format_string: str | None = None,
) -> logging.Logger:
    """
    Setup logging configuration for the agent.
    
    Args:
        level: Logging level
        format_string: Custom format string
        
    Returns:
        Root logger for the discovery_agent package
    """
    if format_string is None:
        format_string = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format=format_string,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
    
    # Get package logger
    logger = logging.getLogger("discovery_agent")
    logger.setLevel(level)
    
    return logger


def now_iso() -> str:
    """Get current time as ISO8601 string in UTC."""
    return datetime.now(timezone.utc).isoformat()


def parse_iso(timestamp: str) -> datetime:
    """Parse ISO8601 timestamp string to datetime."""
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def write_json(path: Path, data: Any, indent: int = 2) -> None:
    """
    Write data to JSON file.
    
    Args:
        path: File path
        data: Data to serialize
        indent: JSON indentation
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False, sort_keys=False)


def read_json(path: Path) -> Any:
    """
    Read JSON file.
    
    Args:
        path: File path
        
    Returns:
        Parsed JSON data
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def truncate_string(s: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate string to maximum length.
    
    Args:
        s: Input string
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated string
    """
    if len(s) <= max_length:
        return s
    return s[: max_length - len(suffix)] + suffix


def format_count(count: int | str) -> str:
    """
    Format a count value for display.
    
    Handles both integers and strings like ">1000".
    """
    if isinstance(count, int):
        return f"{count:,}"
    return str(count)


def estimate_complexity(
    has_ci: bool | str,
    has_lfs: bool | str,
    mr_total: int | str,
    issue_total: int | str,
    archived: bool,
) -> str:
    """
    Estimate migration complexity based on project characteristics.
    
    Args:
        has_ci: Whether project has CI configuration
        has_lfs: Whether project uses LFS
        mr_total: Total merge requests
        issue_total: Total issues
        archived: Whether project is archived
        
    Returns:
        Complexity level: "low", "medium", or "high"
    """
    if archived:
        return "low"  # Archived projects are simpler
    
    score = 0
    
    # CI/CD adds complexity
    if has_ci is True:
        score += 2
    elif has_ci == "unknown":
        score += 1
    
    # LFS adds significant complexity
    if has_lfs is True:
        score += 3
    elif has_lfs == "unknown":
        score += 1
    
    # Large number of MRs indicates active development
    if isinstance(mr_total, int):
        if mr_total > 100:
            score += 2
        elif mr_total > 20:
            score += 1
    elif isinstance(mr_total, str) and mr_total.startswith(">"):
        score += 2
    
    # Large number of issues
    if isinstance(issue_total, int):
        if issue_total > 500:
            score += 2
        elif issue_total > 100:
            score += 1
    elif isinstance(issue_total, str) and issue_total.startswith(">"):
        score += 2
    
    if score >= 5:
        return "high"
    elif score >= 2:
        return "medium"
    return "low"


def identify_blockers(
    has_ci: bool | str,
    has_lfs: bool | str,
    visibility: str,
    errors: list[dict[str, Any]],
) -> list[str]:
    """
    Identify potential migration blockers.
    
    Args:
        has_ci: CI detection result
        has_lfs: LFS detection result
        visibility: Project visibility
        errors: List of discovery errors
        
    Returns:
        List of blocker descriptions
    """
    blockers = []
    
    # CI/CD migration requires workflow conversion
    if has_ci is True:
        blockers.append("Has GitLab CI/CD pipeline - requires conversion to GitHub Actions")
    
    # LFS might need special handling
    if has_lfs is True:
        blockers.append("Uses Git LFS - requires LFS migration setup")
    
    # Internal visibility doesn't exist in GitHub
    if visibility == "internal":
        blockers.append("Internal visibility not available in GitHub - must choose private or public")
    
    # Permission errors
    for error in errors:
        if error.get("status") == 403:
            blockers.append(f"Permission denied for {error.get('step', 'unknown step')}")
    
    return blockers


def generate_notes(
    archived: bool,
    default_branch: str | None,
    mr_counts: dict[str, Any] | str,
    issue_counts: dict[str, Any] | str,
) -> list[str]:
    """
    Generate helpful notes about the project.
    
    Args:
        archived: Whether project is archived
        default_branch: Default branch name
        mr_counts: MR count data
        issue_counts: Issue count data
        
    Returns:
        List of note strings
    """
    notes = []
    
    if archived:
        notes.append("Project is archived - consider keeping archived status after migration")
    
    if default_branch and default_branch not in ("main", "master"):
        notes.append(f"Non-standard default branch: {default_branch}")
    
    if default_branch == "master":
        notes.append("Consider renaming default branch from 'master' to 'main'")
    
    # Open MRs need attention
    if isinstance(mr_counts, dict):
        open_mrs = mr_counts.get("open", 0)
        if isinstance(open_mrs, int) and open_mrs > 0:
            notes.append(f"{open_mrs} open merge requests - consider closing or migrating")
    
    # Open issues
    if isinstance(issue_counts, dict):
        open_issues = issue_counts.get("open", 0)
        if isinstance(open_issues, int) and open_issues > 50:
            notes.append(f"{open_issues} open issues - large issue backlog to migrate")
    
    return notes


class ProgressTracker:
    """Track and display discovery progress."""
    
    def __init__(self, total_groups: int = 0, total_projects: int = 0):
        self.total_groups = total_groups
        self.total_projects = total_projects
        self.completed_groups = 0
        self.completed_projects = 0
        self.current_group: str | None = None
        self.current_project: str | None = None
        self.logger = logging.getLogger("discovery_agent.progress")
    
    def set_totals(self, groups: int, projects: int) -> None:
        """Update total counts."""
        self.total_groups = groups
        self.total_projects = projects
    
    def start_group(self, group_path: str) -> None:
        """Mark start of group processing."""
        self.current_group = group_path
        self.logger.info(f"Processing group: {group_path}")
    
    def complete_group(self) -> None:
        """Mark group as completed."""
        self.completed_groups += 1
        self.logger.info(
            f"Completed group {self.completed_groups}/{self.total_groups}: {self.current_group}"
        )
    
    def start_project(self, project_path: str) -> None:
        """Mark start of project processing."""
        self.current_project = project_path
        self.logger.debug(f"  Processing project: {project_path}")
    
    def complete_project(self) -> None:
        """Mark project as completed."""
        self.completed_projects += 1
        if self.completed_projects % 10 == 0:
            self.logger.info(
                f"Progress: {self.completed_projects}/{self.total_projects} projects"
            )
    
    def log_error(self, message: str) -> None:
        """Log an error."""
        self.logger.error(message)
    
    def summary(self) -> str:
        """Get progress summary string."""
        return (
            f"Completed {self.completed_groups}/{self.total_groups} groups, "
            f"{self.completed_projects}/{self.total_projects} projects"
        )
