"""
GitLab Discovery Agent - Scans GitLab groups and produces inventory/readiness reports.

This is a discovery-only tool for GitLab->GitHub migration planning.
No write operations are performed.
"""

__version__ = "0.1.0"
__author__ = "Discovery Agent Team"

from .gitlab_client import GitLabClient
from .orchestrator import DiscoveryOrchestrator
from .schema import validate_inventory

__all__ = [
    "GitLabClient",
    "DiscoveryOrchestrator",
    "validate_inventory",
    "__version__",
]
