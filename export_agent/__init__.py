"""
GitLab Export Agent - Extracts all data from GitLab projects.

This module provides functionality to export:
- Repository (git bundle, LFS, submodules)
- CI/CD (gitlab-ci.yml, includes, variables, environments, schedules)
- Issues (with comments, attachments, cross-references)
- Merge Requests (with discussions, diffs, approvals)
- Wiki (as git bundle)
- Releases (with assets)
- Packages (metadata and files)
- Settings (protections, members, webhooks, keys)
"""

__version__ = "0.1.0"
__author__ = "Export Agent Team"

from .types import (
    CheckpointState,
    ComponentType,
    ExportProgress,
    ExportResult,
    ExportStatus,
)
from .checkpoint import CheckpointManager
from .repository_exporter import RepositoryExporter
from .cicd_exporter import CICDExporter
from .issues_exporter import IssuesExporter
from .merge_requests_exporter import MergeRequestsExporter
from .wiki_exporter import WikiExporter
from .releases_exporter import ReleasesExporter
from .packages_exporter import PackagesExporter
from .settings_exporter import SettingsExporter

__all__ = [
    "CheckpointManager",
    "CheckpointState",
    "CICDExporter",
    "ComponentType",
    "ExportProgress",
    "ExportResult",
    "ExportStatus",
    "IssuesExporter",
    "MergeRequestsExporter",
    "PackagesExporter",
    "ReleasesExporter",
    "RepositoryExporter",
    "SettingsExporter",
    "WikiExporter",
    "__version__",
]
