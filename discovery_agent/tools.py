"""
GitLab API Tools - Actions the agent can take to gather project information.

All functions use GitLabClient and return structured data for the inventory.
These are the "actions" available to the agent during discovery.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, TypedDict
from urllib.parse import quote

from .gitlab_client import GitLabClient, GitLabClientError

logger = logging.getLogger(__name__)


# Type definitions for tool results
class SubgroupInfo(TypedDict):
    id: int
    full_path: str
    name: str


class ProjectInfo(TypedDict):
    id: int
    path_with_namespace: str
    default_branch: str | None
    archived: bool
    visibility: str


class MRCounts(TypedDict):
    open: int
    merged: int
    closed: int
    total: int


class IssueCounts(TypedDict):
    open: int
    closed: int
    total: int


class HealthCheckResult(TypedDict):
    ok: bool
    version: str | None
    message: str


class TreeEntry(TypedDict):
    id: str
    name: str
    type: str  # "blob", "tree"
    path: str
    mode: str


@dataclass
class ToolResult:
    """Wrapper for tool execution results."""
    success: bool
    data: Any
    error: str | None = None
    status_code: int | None = None


class GitLabTools:
    """
    Collection of GitLab API tools for discovery.
    
    Each tool performs a specific discovery action and returns
    structured data that can be used to populate the inventory.
    """
    
    # Maximum items to count before giving up (for very large projects)
    MAX_COUNT_ITEMS = 10000
    # Maximum items for "light mode" counting
    LIGHT_MODE_LIMIT = 1000
    
    def __init__(self, client: GitLabClient):
        """
        Initialize tools with a GitLab client.
        
        Args:
            client: Configured GitLabClient instance
        """
        self.client = client
    
    def _encode_path(self, path: str) -> str:
        """URL-encode a path for GitLab API."""
        return quote(path, safe="")
    
    def _make_project_path(self, project_id: int | str) -> str:
        """Create API path for a project (handles both ID and path)."""
        if isinstance(project_id, int) or project_id.isdigit():
            return f"/api/v4/projects/{project_id}"
        return f"/api/v4/projects/{self._encode_path(str(project_id))}"
    
    def health_check(self) -> ToolResult:
        """
        Check GitLab instance health and version.
        
        Returns:
            ToolResult with HealthCheckResult data
        """
        try:
            status_code, data, headers = self.client.get("/api/v4/version")
            
            if status_code == 200 and isinstance(data, dict):
                return ToolResult(
                    success=True,
                    data=HealthCheckResult(
                        ok=True,
                        version=data.get("version"),
                        message=f"GitLab {data.get('version', 'unknown')} ({data.get('revision', 'unknown')})",
                    ),
                )
            elif status_code == 401:
                return ToolResult(
                    success=False,
                    data=HealthCheckResult(ok=False, version=None, message="Authentication failed"),
                    error="Invalid or missing token",
                    status_code=status_code,
                )
            else:
                # Version endpoint might not be available, but API might still work
                return ToolResult(
                    success=True,
                    data=HealthCheckResult(
                        ok=True,
                        version=None,
                        message="Version endpoint unavailable, but API accessible",
                    ),
                )
        except GitLabClientError as e:
            return ToolResult(
                success=False,
                data=HealthCheckResult(ok=False, version=None, message=str(e)),
                error=str(e),
                status_code=e.status_code,
            )
    
    def resolve_group_id(self, group: str | int) -> ToolResult:
        """
        Resolve a group path or ID to numeric ID.
        
        Args:
            group: Group full path or numeric ID
            
        Returns:
            ToolResult with numeric group ID
        """
        # If already numeric, verify it exists
        if isinstance(group, int) or (isinstance(group, str) and group.isdigit()):
            group_id = int(group) if isinstance(group, str) else group
            try:
                status_code, data, _ = self.client.get(f"/api/v4/groups/{group_id}")
                if status_code == 200:
                    return ToolResult(success=True, data=data.get("id", group_id))
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Group {group_id} not found",
                    status_code=status_code,
                )
            except GitLabClientError as e:
                return ToolResult(success=False, data=None, error=str(e), status_code=e.status_code)
        
        # Resolve path to ID
        try:
            encoded_path = self._encode_path(str(group))
            status_code, data, _ = self.client.get(f"/api/v4/groups/{encoded_path}")
            
            if status_code == 200 and isinstance(data, dict):
                return ToolResult(success=True, data=data.get("id"))
            
            return ToolResult(
                success=False,
                data=None,
                error=f"Group '{group}' not found",
                status_code=status_code,
            )
        except GitLabClientError as e:
            return ToolResult(success=False, data=None, error=str(e), status_code=e.status_code)
    
    def list_subgroups(self, group_id: int) -> ToolResult:
        """
        List all subgroups of a group.
        
        Args:
            group_id: Parent group ID
            
        Returns:
            ToolResult with list of SubgroupInfo
        """
        try:
            subgroups: list[SubgroupInfo] = []
            
            for item in self.client.paginate(
                f"/api/v4/groups/{group_id}/subgroups",
                params={"all_available": "false"},
            ):
                if isinstance(item, dict):
                    subgroups.append(SubgroupInfo(
                        id=item.get("id"),
                        full_path=item.get("full_path", ""),
                        name=item.get("name", ""),
                    ))
            
            # Sort by full_path for deterministic output
            subgroups.sort(key=lambda x: x["full_path"])
            
            return ToolResult(success=True, data=subgroups)
            
        except GitLabClientError as e:
            return ToolResult(success=False, data=[], error=str(e), status_code=e.status_code)
    
    def list_all_groups(self, top_level_only: bool = True) -> ToolResult:
        """
        List all groups accessible to the current user.
        
        Args:
            top_level_only: If True, return only top-level groups (no parent).
                          If False, return all accessible groups.
            
        Returns:
            ToolResult with list of SubgroupInfo for all accessible groups
        """
        try:
            groups: list[SubgroupInfo] = []
            params = {"all_available": "false"}  # Only groups user is member of
            
            if top_level_only:
                params["top_level_only"] = "true"
            
            for item in self.client.paginate("/api/v4/groups", params=params):
                if isinstance(item, dict):
                    groups.append(SubgroupInfo(
                        id=item.get("id"),
                        full_path=item.get("full_path", ""),
                        name=item.get("name", ""),
                    ))
            
            # Sort by full_path for deterministic output
            groups.sort(key=lambda x: x["full_path"])
            
            logger.info(f"Found {len(groups)} accessible groups (top_level_only={top_level_only})")
            return ToolResult(success=True, data=groups)
            
        except GitLabClientError as e:
            return ToolResult(success=False, data=[], error=str(e), status_code=e.status_code)

    def list_projects(self, group_id: int, include_subgroups: bool = False) -> ToolResult:
        """
        List all projects in a group.
        
        Args:
            group_id: Group ID
            include_subgroups: Whether to include projects from subgroups
            
        Returns:
            ToolResult with list of ProjectInfo
        """
        try:
            projects: list[ProjectInfo] = []
            params = {"include_subgroups": str(include_subgroups).lower()}
            
            for item in self.client.paginate(
                f"/api/v4/groups/{group_id}/projects",
                params=params,
            ):
                if isinstance(item, dict):
                    projects.append(ProjectInfo(
                        id=item.get("id"),
                        path_with_namespace=item.get("path_with_namespace", ""),
                        default_branch=item.get("default_branch"),
                        archived=item.get("archived", False),
                        visibility=item.get("visibility", "private"),
                    ))
            
            # Sort by path for deterministic output
            projects.sort(key=lambda x: x["path_with_namespace"])
            
            return ToolResult(success=True, data=projects)
            
        except GitLabClientError as e:
            return ToolResult(success=False, data=[], error=str(e), status_code=e.status_code)
    
    def get_project(self, project_id: int) -> ToolResult:
        """
        Get detailed project information.
        
        Args:
            project_id: Project ID
            
        Returns:
            ToolResult with project details (subset of fields)
        """
        try:
            path = self._make_project_path(project_id)
            status_code, data, _ = self.client.get(path)
            
            if status_code == 200 and isinstance(data, dict):
                # Extract only relevant fields
                project_data = {
                    "id": data.get("id"),
                    "path_with_namespace": data.get("path_with_namespace"),
                    "name": data.get("name"),
                    "default_branch": data.get("default_branch"),
                    "archived": data.get("archived", False),
                    "visibility": data.get("visibility"),
                    "created_at": data.get("created_at"),
                    "last_activity_at": data.get("last_activity_at"),
                    "empty_repo": data.get("empty_repo", False),
                    "repository_access_level": data.get("repository_access_level"),
                    "issues_enabled": data.get("issues_enabled", True),
                    "merge_requests_enabled": data.get("merge_requests_enabled", True),
                    "wiki_enabled": data.get("wiki_enabled", False),
                    "snippets_enabled": data.get("snippets_enabled", False),
                    "container_registry_enabled": data.get("container_registry_enabled", False),
                    "lfs_enabled": data.get("lfs_enabled", False),
                    "statistics": data.get("statistics"),
                }
                return ToolResult(success=True, data=project_data)
            
            return ToolResult(
                success=False,
                data=None,
                error=f"Project {project_id} not found",
                status_code=status_code,
            )
            
        except GitLabClientError as e:
            return ToolResult(success=False, data=None, error=str(e), status_code=e.status_code)
    
    def get_file(
        self,
        project_id: int,
        file_path: str,
        ref: str | None = None,
    ) -> ToolResult:
        """
        Get file content from repository.
        
        Args:
            project_id: Project ID
            file_path: Path to file in repository
            ref: Branch/tag/commit (defaults to default branch)
            
        Returns:
            ToolResult with file content as text
        """
        try:
            encoded_file = self._encode_path(file_path)
            path = f"/api/v4/projects/{project_id}/repository/files/{encoded_file}/raw"
            params = {}
            if ref:
                params["ref"] = ref
            
            status_code, data, _ = self.client.get(path, params)
            
            if status_code == 200:
                content = data if isinstance(data, str) else str(data)
                return ToolResult(success=True, data=content)
            elif status_code == 404:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"File '{file_path}' not found",
                    status_code=status_code,
                )
            else:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Failed to read file: HTTP {status_code}",
                    status_code=status_code,
                )
                
        except GitLabClientError as e:
            return ToolResult(success=False, data=None, error=str(e), status_code=e.status_code)
    
    def get_repository_tree(
        self,
        project_id: int,
        ref: str | None = None,
        path: str = "",
        recursive: bool = False,
    ) -> ToolResult:
        """
        Get repository tree (file listing).
        
        Args:
            project_id: Project ID
            ref: Branch/tag/commit
            path: Directory path (empty for root)
            recursive: Whether to get tree recursively
            
        Returns:
            ToolResult with list of TreeEntry
        """
        try:
            entries: list[TreeEntry] = []
            params: dict[str, Any] = {}
            if ref:
                params["ref"] = ref
            if path:
                params["path"] = path
            if recursive:
                params["recursive"] = "true"
            
            for item in self.client.paginate(
                f"/api/v4/projects/{project_id}/repository/tree",
                params=params,
            ):
                if isinstance(item, dict):
                    entries.append(TreeEntry(
                        id=item.get("id", ""),
                        name=item.get("name", ""),
                        type=item.get("type", ""),
                        path=item.get("path", ""),
                        mode=item.get("mode", ""),
                    ))
            
            return ToolResult(success=True, data=entries)
            
        except GitLabClientError as e:
            return ToolResult(success=False, data=[], error=str(e), status_code=e.status_code)
    
    def get_merge_request_counts(
        self,
        project_id: int,
        light_mode: bool = True,
    ) -> ToolResult:
        """
        Get merge request counts by state.
        
        Args:
            project_id: Project ID
            light_mode: If True, use efficient counting with headers/limited pages
            
        Returns:
            ToolResult with MRCounts or "unknown" for exceeded limits
        """
        try:
            base_path = f"/api/v4/projects/{project_id}/merge_requests"
            max_items = self.LIGHT_MODE_LIMIT if light_mode else self.MAX_COUNT_ITEMS
            
            counts: dict[str, int | str] = {}
            total = 0
            exceeded = False
            
            for state in ["opened", "merged", "closed"]:
                count, is_exact = self.client.get_paginated_count(
                    base_path,
                    params={"state": state},
                    max_count=max_items,
                )
                
                key = "open" if state == "opened" else state
                counts[key] = count
                total += count
                
                if not is_exact:
                    exceeded = True
                    counts[key] = f">{count}"
            
            if exceeded:
                return ToolResult(
                    success=True,
                    data={
                        "open": counts.get("open", 0),
                        "merged": counts.get("merged", 0),
                        "closed": counts.get("closed", 0),
                        "total": f">{total}",
                        "note": f"Counts may exceed {max_items} limit",
                    },
                )
            
            return ToolResult(
                success=True,
                data=MRCounts(
                    open=counts.get("open", 0),
                    merged=counts.get("merged", 0),
                    closed=counts.get("closed", 0),
                    total=total,
                ),
            )
            
        except GitLabClientError as e:
            return ToolResult(success=False, data="unknown", error=str(e), status_code=e.status_code)
    
    def get_issue_counts(
        self,
        project_id: int,
        light_mode: bool = True,
    ) -> ToolResult:
        """
        Get issue counts by state.
        
        Args:
            project_id: Project ID
            light_mode: If True, use efficient counting
            
        Returns:
            ToolResult with IssueCounts
        """
        try:
            base_path = f"/api/v4/projects/{project_id}/issues"
            max_items = self.LIGHT_MODE_LIMIT if light_mode else self.MAX_COUNT_ITEMS
            
            counts: dict[str, int | str] = {}
            total = 0
            exceeded = False
            
            for state in ["opened", "closed"]:
                count, is_exact = self.client.get_paginated_count(
                    base_path,
                    params={"state": state},
                    max_count=max_items,
                )
                
                key = "open" if state == "opened" else state
                counts[key] = count
                total += count
                
                if not is_exact:
                    exceeded = True
            
            if exceeded:
                return ToolResult(
                    success=True,
                    data={
                        "open": counts.get("open", 0),
                        "closed": counts.get("closed", 0),
                        "total": f">{total}",
                        "note": f"Counts may exceed {max_items} limit",
                    },
                )
            
            return ToolResult(
                success=True,
                data=IssueCounts(
                    open=counts.get("open", 0),
                    closed=counts.get("closed", 0),
                    total=total,
                ),
            )
            
        except GitLabClientError as e:
            return ToolResult(success=False, data="unknown", error=str(e), status_code=e.status_code)
    
    def detect_lfs(self, project_id: int, ref: str | None = None) -> ToolResult:
        """
        Detect if project uses Git LFS.
        
        Checks for:
        1. .gitattributes file containing "filter=lfs"
        2. LFS enabled in project settings (from get_project)
        
        Args:
            project_id: Project ID
            ref: Branch/tag/commit
            
        Returns:
            ToolResult with boolean or "unknown"
        """
        try:
            # Check .gitattributes for LFS filter
            result = self.get_file(project_id, ".gitattributes", ref)
            
            if result.success and result.data:
                content = str(result.data)
                if "filter=lfs" in content:
                    return ToolResult(success=True, data=True)
            
            # File not found or no LFS markers
            if result.status_code == 404 or (result.success and not result.data):
                return ToolResult(success=True, data=False)
            
            # If we couldn't read the file for other reasons, check project settings
            project_result = self.get_project(project_id)
            if project_result.success and project_result.data:
                lfs_enabled = project_result.data.get("lfs_enabled", False)
                return ToolResult(success=True, data=lfs_enabled)
            
            return ToolResult(success=True, data="unknown", error=result.error)
            
        except GitLabClientError as e:
            return ToolResult(success=False, data="unknown", error=str(e), status_code=e.status_code)
    
    def detect_ci(self, project_id: int, ref: str | None = None) -> ToolResult:
        """
        Detect if project has CI/CD configuration.
        
        Checks for .gitlab-ci.yml in repository.
        
        Args:
            project_id: Project ID
            ref: Branch/tag/commit
            
        Returns:
            ToolResult with boolean or "unknown"
        """
        try:
            result = self.get_file(project_id, ".gitlab-ci.yml", ref)
            
            if result.success:
                return ToolResult(success=True, data=True)
            elif result.status_code == 404:
                return ToolResult(success=True, data=False)
            elif result.status_code == 403:
                return ToolResult(
                    success=True,
                    data="unknown",
                    error="Missing repository read permissions",
                    status_code=403,
                )
            else:
                return ToolResult(
                    success=True,
                    data="unknown",
                    error=result.error,
                    status_code=result.status_code,
                )
                
        except GitLabClientError as e:
            return ToolResult(success=False, data="unknown", error=str(e), status_code=e.status_code)
    
    def sample_ci(
        self,
        project_id: int,
        ref: str | None = None,
        max_lines: int = 200,
    ) -> ToolResult:
        """
        Get sample of CI configuration file.
        
        Args:
            project_id: Project ID
            ref: Branch/tag/commit
            max_lines: Maximum lines to return
            
        Returns:
            ToolResult with first N lines of .gitlab-ci.yml
        """
        try:
            result = self.get_file(project_id, ".gitlab-ci.yml", ref)
            
            if not result.success:
                return result
            
            content = str(result.data)
            lines = content.splitlines()[:max_lines]
            truncated = len(content.splitlines()) > max_lines
            
            return ToolResult(
                success=True,
                data={
                    "content": "\n".join(lines),
                    "truncated": truncated,
                    "total_lines": len(content.splitlines()),
                },
            )
            
        except GitLabClientError as e:
            return ToolResult(success=False, data=None, error=str(e), status_code=e.status_code)

    # =========================================================================
    # Deep Analysis Methods (for --deep mode)
    # =========================================================================
    
    def get_branches_count(self, project_id: int) -> ToolResult:
        """
        Get count of branches using X-Total header for efficiency.
        
        Args:
            project_id: Project ID
            
        Returns:
            ToolResult with branch count (int) or "unknown"
        """
        try:
            path = f"/api/v4/projects/{project_id}/repository/branches"
            # Use per_page=1 to get just the header
            status_code, data, headers = self.client.get(path, params={"per_page": "1"})
            
            if status_code == 200:
                # Try X-Total header first (most efficient)
                total = headers.get("x-total")
                if total is not None:
                    try:
                        return ToolResult(success=True, data=int(total))
                    except ValueError:
                        pass
                
                # Fallback: count with pagination (limited)
                count, is_exact = self.client.get_paginated_count(
                    path, params={}, max_count=500
                )
                if is_exact:
                    return ToolResult(success=True, data=count)
                return ToolResult(success=True, data=f">{count}")
            
            elif status_code == 404:
                # Empty repository
                return ToolResult(success=True, data=0)
            else:
                return ToolResult(
                    success=False,
                    data="unknown",
                    error=f"HTTP {status_code}",
                    status_code=status_code,
                )
                
        except GitLabClientError as e:
            return ToolResult(success=False, data="unknown", error=str(e), status_code=e.status_code)
    
    def get_tags_count(self, project_id: int) -> ToolResult:
        """
        Get count of tags using X-Total header for efficiency.
        
        Args:
            project_id: Project ID
            
        Returns:
            ToolResult with tag count (int) or "unknown"
        """
        try:
            path = f"/api/v4/projects/{project_id}/repository/tags"
            status_code, data, headers = self.client.get(path, params={"per_page": "1"})
            
            if status_code == 200:
                total = headers.get("x-total")
                if total is not None:
                    try:
                        return ToolResult(success=True, data=int(total))
                    except ValueError:
                        pass
                
                # Fallback: count with pagination
                count, is_exact = self.client.get_paginated_count(
                    path, params={}, max_count=500
                )
                if is_exact:
                    return ToolResult(success=True, data=count)
                return ToolResult(success=True, data=f">{count}")
            
            elif status_code == 404:
                return ToolResult(success=True, data=0)
            else:
                return ToolResult(
                    success=False,
                    data="unknown",
                    error=f"HTTP {status_code}",
                    status_code=status_code,
                )
                
        except GitLabClientError as e:
            return ToolResult(success=False, data="unknown", error=str(e), status_code=e.status_code)
    
    def detect_submodules(self, project_id: int, ref: str | None = None) -> ToolResult:
        """
        Detect if project uses Git submodules.
        
        Checks for .gitmodules file in repository root.
        
        Args:
            project_id: Project ID
            ref: Branch/tag/commit
            
        Returns:
            ToolResult with boolean or "unknown"
        """
        try:
            result = self.get_file(project_id, ".gitmodules", ref)
            
            if result.success and result.data:
                # File exists and has content
                return ToolResult(success=True, data=True)
            elif result.status_code == 404:
                return ToolResult(success=True, data=False)
            else:
                return ToolResult(
                    success=True,
                    data="unknown",
                    error=result.error,
                    status_code=result.status_code,
                )
                
        except GitLabClientError as e:
            return ToolResult(success=False, data="unknown", error=str(e), status_code=e.status_code)
    
    def get_ci_content(
        self,
        project_id: int,
        ref: str | None = None,
        max_lines: int = 400,
    ) -> ToolResult:
        """
        Get CI configuration file content for parsing.
        
        Args:
            project_id: Project ID
            ref: Branch/tag/commit
            max_lines: Maximum lines to return
            
        Returns:
            ToolResult with CI content dict containing:
            - content: str (up to max_lines)
            - truncated: bool
            - total_lines: int
        """
        try:
            result = self.get_file(project_id, ".gitlab-ci.yml", ref)
            
            if not result.success:
                if result.status_code == 404:
                    return ToolResult(success=True, data=None)  # No CI file
                return result
            
            content = str(result.data)
            all_lines = content.splitlines()
            lines = all_lines[:max_lines]
            truncated = len(all_lines) > max_lines
            
            return ToolResult(
                success=True,
                data={
                    "content": "\n".join(lines),
                    "truncated": truncated,
                    "total_lines": len(all_lines),
                },
            )
            
        except GitLabClientError as e:
            return ToolResult(success=False, data=None, error=str(e), status_code=e.status_code)
    
    def get_efficient_mr_counts(self, project_id: int) -> ToolResult:
        """
        Get MR counts using X-Total header for efficiency.
        
        Uses single request per state with per_page=1 to minimize API load.
        
        Args:
            project_id: Project ID
            
        Returns:
            ToolResult with MRCounts
        """
        try:
            base_path = f"/api/v4/projects/{project_id}/merge_requests"
            counts = {"open": 0, "merged": 0, "closed": 0}
            
            for state in ["opened", "merged", "closed"]:
                status_code, _, headers = self.client.get(
                    base_path,
                    params={"state": state, "per_page": "1"},
                )
                
                if status_code == 200:
                    total = headers.get("x-total")
                    if total is not None:
                        try:
                            key = "open" if state == "opened" else state
                            counts[key] = int(total)
                        except ValueError:
                            pass
            
            total = counts["open"] + counts["merged"] + counts["closed"]
            
            return ToolResult(
                success=True,
                data=MRCounts(
                    open=counts["open"],
                    merged=counts["merged"],
                    closed=counts["closed"],
                    total=total,
                ),
            )
            
        except GitLabClientError as e:
            return ToolResult(success=False, data="unknown", error=str(e), status_code=e.status_code)
    
    def get_efficient_issue_counts(self, project_id: int) -> ToolResult:
        """
        Get issue counts using X-Total header for efficiency.
        
        Args:
            project_id: Project ID
            
        Returns:
            ToolResult with IssueCounts
        """
        try:
            base_path = f"/api/v4/projects/{project_id}/issues"
            counts = {"open": 0, "closed": 0}
            
            for state in ["opened", "closed"]:
                status_code, _, headers = self.client.get(
                    base_path,
                    params={"state": state, "per_page": "1"},
                )
                
                if status_code == 200:
                    total = headers.get("x-total")
                    if total is not None:
                        try:
                            key = "open" if state == "opened" else state
                            counts[key] = int(total)
                        except ValueError:
                            pass
            
            total = counts["open"] + counts["closed"]
            
            return ToolResult(
                success=True,
                data=IssueCounts(
                    open=counts["open"],
                    closed=counts["closed"],
                    total=total,
                ),
            )
            
        except GitLabClientError as e:
            return ToolResult(success=False, data="unknown", error=str(e), status_code=e.status_code)

    # =========================================================================
    # v2 Enrichment Tools (for accurate pricing)
    # =========================================================================
    
    def get_protected_branches_count(self, project_id: int) -> ToolResult:
        """
        Get count of protected branches using X-Total header.
        
        Args:
            project_id: Project ID
            
        Returns:
            ToolResult with count (int) or "unknown"
        """
        try:
            path = f"/api/v4/projects/{project_id}/protected_branches"
            status_code, data, headers = self.client.get(path, params={"per_page": "1"})
            
            if status_code == 200:
                total = headers.get("x-total")
                if total is not None:
                    try:
                        return ToolResult(success=True, data=int(total))
                    except ValueError:
                        pass
                
                # Fallback: count from response if small
                if isinstance(data, list) and len(data) <= 20:
                    count, _ = self.client.get_paginated_count(path, {}, max_count=100)
                    return ToolResult(success=True, data=count)
                    
                return ToolResult(success=True, data="unknown")
            
            elif status_code == 403:
                return ToolResult(
                    success=False,
                    data="unknown",
                    error="No permission to read protected branches",
                    status_code=403,
                )
            else:
                return ToolResult(
                    success=False,
                    data="unknown",
                    error=f"HTTP {status_code}",
                    status_code=status_code,
                )
                
        except GitLabClientError as e:
            return ToolResult(success=False, data="unknown", error=str(e), status_code=e.status_code)
    
    def get_project_variables_count(self, project_id: int) -> ToolResult:
        """
        Get count of CI/CD variables (NOT values) using X-Total header.
        
        Args:
            project_id: Project ID
            
        Returns:
            ToolResult with count (int) or "unknown"
        """
        try:
            path = f"/api/v4/projects/{project_id}/variables"
            status_code, data, headers = self.client.get(path, params={"per_page": "1"})
            
            if status_code == 200:
                total = headers.get("x-total")
                if total is not None:
                    try:
                        return ToolResult(success=True, data=int(total))
                    except ValueError:
                        pass
                
                # Fallback
                if isinstance(data, list):
                    count, _ = self.client.get_paginated_count(path, {}, max_count=100)
                    return ToolResult(success=True, data=count)
                    
                return ToolResult(success=True, data=0)
            
            elif status_code == 403:
                return ToolResult(
                    success=False,
                    data="unknown",
                    error="No permission to read CI variables",
                    status_code=403,
                )
            else:
                return ToolResult(
                    success=False,
                    data="unknown",
                    error=f"HTTP {status_code}",
                    status_code=status_code,
                )
                
        except GitLabClientError as e:
            return ToolResult(success=False, data="unknown", error=str(e), status_code=e.status_code)
    
    def get_group_variables_count(self, group_id: int) -> ToolResult:
        """
        Get count of group CI/CD variables (NOT values).
        
        Args:
            group_id: Group ID
            
        Returns:
            ToolResult with count (int) or "unknown"
        """
        try:
            path = f"/api/v4/groups/{group_id}/variables"
            status_code, data, headers = self.client.get(path, params={"per_page": "1"})
            
            if status_code == 200:
                total = headers.get("x-total")
                if total is not None:
                    try:
                        return ToolResult(success=True, data=int(total))
                    except ValueError:
                        pass
                
                if isinstance(data, list):
                    count, _ = self.client.get_paginated_count(path, {}, max_count=100)
                    return ToolResult(success=True, data=count)
                    
                return ToolResult(success=True, data=0)
            
            elif status_code == 403:
                return ToolResult(
                    success=False,
                    data="unknown",
                    error="No permission to read group variables",
                    status_code=403,
                )
            else:
                return ToolResult(
                    success=False,
                    data="unknown",
                    error=f"HTTP {status_code}",
                    status_code=status_code,
                )
                
        except GitLabClientError as e:
            return ToolResult(success=False, data="unknown", error=str(e), status_code=e.status_code)
    
    def get_webhooks_count(self, project_id: int) -> ToolResult:
        """
        Get count of project webhooks.
        
        Args:
            project_id: Project ID
            
        Returns:
            ToolResult with count (int) or "unknown"
        """
        try:
            path = f"/api/v4/projects/{project_id}/hooks"
            status_code, data, headers = self.client.get(path, params={"per_page": "1"})
            
            if status_code == 200:
                total = headers.get("x-total")
                if total is not None:
                    try:
                        return ToolResult(success=True, data=int(total))
                    except ValueError:
                        pass
                
                if isinstance(data, list):
                    count, _ = self.client.get_paginated_count(path, {}, max_count=50)
                    return ToolResult(success=True, data=count)
                    
                return ToolResult(success=True, data=0)
            
            elif status_code == 403:
                return ToolResult(
                    success=False,
                    data="unknown",
                    error="No permission to read webhooks",
                    status_code=403,
                )
            else:
                return ToolResult(
                    success=False,
                    data="unknown",
                    error=f"HTTP {status_code}",
                    status_code=status_code,
                )
                
        except GitLabClientError as e:
            return ToolResult(success=False, data="unknown", error=str(e), status_code=e.status_code)
    
    def get_releases_count(self, project_id: int) -> ToolResult:
        """
        Get count of releases using X-Total header.
        
        Args:
            project_id: Project ID
            
        Returns:
            ToolResult with count (int) or "unknown"
        """
        try:
            path = f"/api/v4/projects/{project_id}/releases"
            status_code, data, headers = self.client.get(path, params={"per_page": "1"})
            
            if status_code == 200:
                total = headers.get("x-total")
                if total is not None:
                    try:
                        return ToolResult(success=True, data=int(total))
                    except ValueError:
                        pass
                
                if isinstance(data, list):
                    count, _ = self.client.get_paginated_count(path, {}, max_count=200)
                    return ToolResult(success=True, data=count)
                    
                return ToolResult(success=True, data=0)
            
            elif status_code == 404:
                # No releases endpoint or empty
                return ToolResult(success=True, data=0)
            else:
                return ToolResult(
                    success=False,
                    data="unknown",
                    error=f"HTTP {status_code}",
                    status_code=status_code,
                )
                
        except GitLabClientError as e:
            return ToolResult(success=False, data="unknown", error=str(e), status_code=e.status_code)
    
    def detect_codeowners(self, project_id: int, ref: str | None = None) -> ToolResult:
        """
        Detect if project has CODEOWNERS file.
        
        Checks common locations: CODEOWNERS, .gitlab/CODEOWNERS, docs/CODEOWNERS
        
        Args:
            project_id: Project ID
            ref: Branch/tag/commit
            
        Returns:
            ToolResult with boolean or "unknown"
        """
        codeowners_paths = [
            "CODEOWNERS",
            ".gitlab/CODEOWNERS",
            "docs/CODEOWNERS",
        ]
        
        for path in codeowners_paths:
            try:
                result = self.get_file(project_id, path, ref)
                if result.success and result.data:
                    return ToolResult(success=True, data=True)
                elif result.status_code == 403:
                    return ToolResult(
                        success=True,
                        data="unknown",
                        error="No permission",
                        status_code=403,
                    )
            except GitLabClientError:
                continue
        
        return ToolResult(success=True, data=False)
    
    def detect_public_folder(self, project_id: int, ref: str | None = None) -> ToolResult:
        """
        Detect if project has public/ folder (GitLab Pages hint).
        
        Args:
            project_id: Project ID
            ref: Branch/tag/commit
            
        Returns:
            ToolResult with boolean or "unknown"
        """
        try:
            result = self.get_repository_tree(project_id, ref=ref, path="", recursive=False)
            
            if result.success and isinstance(result.data, list):
                for entry in result.data:
                    if entry.get("name") == "public" and entry.get("type") == "tree":
                        return ToolResult(success=True, data=True)
                return ToolResult(success=True, data=False)
            
            elif result.status_code == 403:
                return ToolResult(
                    success=True,
                    data="unknown",
                    error="No permission",
                    status_code=403,
                )
            else:
                return ToolResult(success=True, data="unknown", error=result.error)
                
        except GitLabClientError as e:
            return ToolResult(success=False, data="unknown", error=str(e), status_code=e.status_code)
    
    def detect_container_files(self, project_id: int, ref: str | None = None) -> ToolResult:
        """
        Detect if project has container-related files (Dockerfile, helm, k8s).
        
        This is a heuristic for container registry usage.
        
        Args:
            project_id: Project ID
            ref: Branch/tag/commit
            
        Returns:
            ToolResult with dict of detected files
        """
        files_to_check = ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"]
        folders_to_check = ["helm", "k8s", "kubernetes", "charts"]
        
        detected = {
            "has_dockerfile": False,
            "has_compose": False,
            "has_k8s": False,
        }
        
        try:
            result = self.get_repository_tree(project_id, ref=ref, path="", recursive=False)
            
            if not result.success:
                if result.status_code == 403:
                    return ToolResult(
                        success=True,
                        data={"has_dockerfile": "unknown", "has_compose": "unknown", "has_k8s": "unknown"},
                        error="No permission",
                        status_code=403,
                    )
                return ToolResult(success=True, data=detected)
            
            if isinstance(result.data, list):
                for entry in result.data:
                    name = entry.get("name", "").lower()
                    entry_type = entry.get("type")
                    
                    if name == "dockerfile":
                        detected["has_dockerfile"] = True
                    elif name in ["docker-compose.yml", "docker-compose.yaml"]:
                        detected["has_compose"] = True
                    elif entry_type == "tree" and name in folders_to_check:
                        detected["has_k8s"] = True
            
            return ToolResult(success=True, data=detected)
            
        except GitLabClientError as e:
            return ToolResult(success=False, data=detected, error=str(e), status_code=e.status_code)
    
    def get_project_features(self, project_id: int) -> ToolResult:
        """
        Get project feature flags (registry, pages, wiki enabled).
        
        This is more efficient than get_project for just features.
        
        Args:
            project_id: Project ID
            
        Returns:
            ToolResult with feature flags dict
        """
        try:
            path = self._make_project_path(project_id)
            status_code, data, _ = self.client.get(path)
            
            if status_code == 200 and isinstance(data, dict):
                features = {
                    "container_registry_enabled": data.get("container_registry_enabled", False),
                    "packages_enabled": data.get("packages_enabled", False),
                    "wiki_enabled": data.get("wiki_enabled", False),
                    "pages_access_level": data.get("pages_access_level", "disabled"),
                    "issues_enabled": data.get("issues_enabled", True),
                    "merge_requests_enabled": data.get("merge_requests_enabled", True),
                    "lfs_enabled": data.get("lfs_enabled", False),
                    "last_activity_at": data.get("last_activity_at"),
                }
                return ToolResult(success=True, data=features)
            
            return ToolResult(
                success=False,
                data=None,
                error=f"HTTP {status_code}",
                status_code=status_code,
            )
            
        except GitLabClientError as e:
            return ToolResult(success=False, data=None, error=str(e), status_code=e.status_code)
