"""
Type definitions for the Export Agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class ExportStatus(str, Enum):
    """Status of an export operation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ComponentType(str, Enum):
    """Types of components that can be exported."""
    REPOSITORY = "repository"
    CI_CD = "ci_cd"
    ISSUES = "issues"
    MERGE_REQUESTS = "merge_requests"
    WIKI = "wiki"
    RELEASES = "releases"
    PACKAGES = "packages"
    SETTINGS = "settings"


@dataclass
class ExportProgress:
    """Progress information for an export component."""
    component: ComponentType
    status: ExportStatus
    message: str
    current: int = 0
    total: int = 0
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "component": self.component.value,
            "status": self.status.value,
            "message": self.message,
            "current": self.current,
            "total": self.total,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "error": self.error,
        }


@dataclass
class ExportResult:
    """Result of an export operation."""
    project_id: int
    project_path: str
    run_id: str
    output_dir: Path
    status: ExportStatus
    components: Dict[ComponentType, ExportProgress] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    total_size_bytes: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "project_id": self.project_id,
            "project_path": self.project_path,
            "run_id": self.run_id,
            "output_dir": str(self.output_dir),
            "status": self.status.value,
            "components": {
                k.value: v.to_dict() for k, v in self.components.items()
            },
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "total_size_bytes": self.total_size_bytes,
            "errors": self.errors,
        }


@dataclass
class CheckpointState:
    """State for resuming an export."""
    project_id: int
    run_id: str
    completed_components: List[ComponentType] = field(default_factory=list)
    last_checkpoint_at: Optional[datetime] = None
    partial_state: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "project_id": self.project_id,
            "run_id": self.run_id,
            "completed_components": [c.value for c in self.completed_components],
            "last_checkpoint_at": self.last_checkpoint_at.isoformat() if self.last_checkpoint_at else None,
            "partial_state": self.partial_state,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CheckpointState:
        """Create from dictionary."""
        return cls(
            project_id=data["project_id"],
            run_id=data["run_id"],
            completed_components=[ComponentType(c) for c in data.get("completed_components", [])],
            last_checkpoint_at=datetime.fromisoformat(data["last_checkpoint_at"]) if data.get("last_checkpoint_at") else None,
            partial_state=data.get("partial_state", {}),
        )
