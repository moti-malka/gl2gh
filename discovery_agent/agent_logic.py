"""
Agent Logic - Decision-making and planning for discovery.

Implements a rule-based agent that decides what actions to take
based on current state and missing data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from .tools import GitLabTools, ToolResult
from .utils import estimate_complexity, identify_blockers, generate_notes

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of actions the agent can take."""
    RESOLVE_GROUP = auto()
    RESOLVE_PROJECT = auto()  # For single-project mode
    LIST_ALL_GROUPS = auto()  # For discover-all mode
    LIST_SUBGROUPS = auto()
    LIST_PROJECTS = auto()
    GET_PROJECT_DETAILS = auto()
    DETECT_CI = auto()
    DETECT_LFS = auto()
    GET_MR_COUNTS = auto()
    GET_ISSUE_COUNTS = auto()
    SAMPLE_CI = auto()
    HEALTH_CHECK = auto()
    COMPLETE_PROJECT = auto()
    COMPLETE_GROUP = auto()
    DONE = auto()


@dataclass
class Action:
    """Represents an action for the agent to take."""
    action_type: ActionType
    target_id: int | str | None = None
    target_path: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    priority: int = 0  # Lower = higher priority


@dataclass
class ProjectState:
    """Tracks discovery state for a single project."""
    id: int
    path_with_namespace: str
    default_branch: str | None
    archived: bool
    visibility: str
    group_id: int
    
    # Discovery progress
    details_fetched: bool = False
    ci_checked: bool = False
    lfs_checked: bool = False
    mr_counts_fetched: bool = False
    issue_counts_fetched: bool = False
    
    # Discovered facts
    has_ci: bool | str = "unknown"
    has_lfs: bool | str = "unknown"
    mr_counts: dict[str, Any] | str = field(default_factory=lambda: "unknown")
    issue_counts: dict[str, Any] | str = field(default_factory=lambda: "unknown")
    ci_sample: dict[str, Any] | None = None
    
    # Deep analysis data (populated when --deep is used)
    repo_profile: dict[str, Any] | None = None
    ci_profile: dict[str, Any] | None = None
    migration_estimate: dict[str, Any] | None = None
    wiki_enabled: bool = False
    
    # Errors encountered
    errors: list[dict[str, Any]] = field(default_factory=list)
    
    # API call tracking
    api_calls_used: int = 0
    
    @property
    def is_complete(self) -> bool:
        """Check if all discovery tasks are complete for this project."""
        return (
            self.details_fetched
            and self.ci_checked
            and self.lfs_checked
            and self.mr_counts_fetched
            and self.issue_counts_fetched
        )
    
    def add_error(self, step: str, message: str, status: int | None = None) -> None:
        """Record an error."""
        self.errors.append({
            "step": step,
            "status": status,
            "message": message,
        })


@dataclass
class GroupState:
    """Tracks discovery state for a group."""
    id: int
    full_path: str
    
    # Discovery progress
    subgroups_listed: bool = False
    projects_listed: bool = False
    
    # Discovered data
    subgroup_ids: list[int] = field(default_factory=list)
    project_ids: list[int] = field(default_factory=list)


@dataclass
class AgentState:
    """
    Complete state of the discovery agent.
    
    Tracks what has been discovered and what remains.
    """
    # Root group
    root_group_id: int | None = None
    root_group_path: str = ""
    
    # Groups
    groups: dict[int, GroupState] = field(default_factory=dict)
    pending_groups: list[int] = field(default_factory=list)
    completed_groups: set[int] = field(default_factory=set)
    
    # Projects
    projects: dict[int, ProjectState] = field(default_factory=dict)
    pending_projects: list[int] = field(default_factory=list)
    completed_projects: set[int] = field(default_factory=set)
    
    # Budgets
    total_api_calls: int = 0
    max_api_calls: int = 5000
    max_per_project_calls: int = 200
    
    # Flags
    health_checked: bool = False
    is_budget_exceeded: bool = False
    discover_all_mode: bool = False  # True when discovering all accessible groups
    all_groups_listed: bool = False  # True after listing all accessible groups
    single_project_mode: bool = False  # True when scanning a single project
    single_project_path: str = ""  # Project path for single-project mode
    single_project_resolved: bool = False  # True after resolving single project
    
    @property
    def is_complete(self) -> bool:
        """Check if discovery is complete."""
        # In single-project mode, just check if the project is done
        if self.single_project_mode:
            return (
                not self.pending_projects
                and self.single_project_resolved
            )
        # In discover-all mode, we don't need a root group
        if self.discover_all_mode:
            return (
                not self.pending_groups
                and not self.pending_projects
                and self.all_groups_listed
            )
        return (
            not self.pending_groups
            and not self.pending_projects
            and self.root_group_id is not None
        )
    
    def register_api_call(self, project_id: int | None = None) -> bool:
        """
        Register an API call and check budget.
        
        Returns:
            True if within budget, False if exceeded
        """
        self.total_api_calls += 1
        
        if project_id is not None and project_id in self.projects:
            self.projects[project_id].api_calls_used += 1
            if self.projects[project_id].api_calls_used > self.max_per_project_calls:
                logger.warning(f"Per-project budget exceeded for project {project_id}")
        
        if self.total_api_calls >= self.max_api_calls:
            self.is_budget_exceeded = True
            logger.warning(f"Total API call budget exceeded ({self.max_api_calls})")
            return False
        
        return True


class AgentPlanner:
    """
    Plans actions based on current state.
    
    Implements a simple rule-based planner that decides what
    the agent should do next based on missing data.
    """
    
    def __init__(self, state: AgentState, tools: GitLabTools):
        self.state = state
        self.tools = tools
    
    def get_next_actions(self, max_actions: int = 1) -> list[Action]:
        """
        Determine next actions to take.
        
        Args:
            max_actions: Maximum number of actions to return
            
        Returns:
            List of actions to execute
        """
        if self.state.is_budget_exceeded:
            return [Action(ActionType.DONE)]
        
        actions: list[Action] = []
        
        # Priority 0: Health check first
        if not self.state.health_checked:
            actions.append(Action(ActionType.HEALTH_CHECK, priority=0))
            return actions[:max_actions]
        
        # Priority 1: In single-project mode, resolve the project first
        if self.state.single_project_mode and not self.state.single_project_resolved:
            actions.append(Action(
                ActionType.RESOLVE_PROJECT,
                target_path=self.state.single_project_path,
                priority=1,
            ))
            return actions[:max_actions]
        
        # Priority 1: In discover-all mode, list all accessible groups first
        if self.state.discover_all_mode and not self.state.all_groups_listed:
            actions.append(Action(
                ActionType.LIST_ALL_GROUPS,
                priority=1,
            ))
            return actions[:max_actions]
        
        # Priority 1: Resolve root group (only if not in discover-all mode or single-project mode)
        if not self.state.discover_all_mode and not self.state.single_project_mode and self.state.root_group_id is None:
            actions.append(Action(
                ActionType.RESOLVE_GROUP,
                target_path=self.state.root_group_path,
                priority=1,
            ))
            return actions[:max_actions]
        
        # Priority 2: Process pending groups (discover structure) - skip in single-project mode
        if not self.state.single_project_mode:
            for group_id in self.state.pending_groups:
                group = self.state.groups.get(group_id)
                if group is None:
                    continue
                
                if not group.subgroups_listed:
                    actions.append(Action(
                        ActionType.LIST_SUBGROUPS,
                        target_id=group_id,
                        target_path=group.full_path,
                        priority=2,
                    ))
                
                if not group.projects_listed:
                    actions.append(Action(
                        ActionType.LIST_PROJECTS,
                        target_id=group_id,
                        target_path=group.full_path,
                        priority=2,
                    ))
        
        # Priority 3: Process pending projects (gather facts)
        for project_id in self.state.pending_projects:
            project = self.state.projects.get(project_id)
            if project is None:
                continue
            
            # Check per-project budget
            if project.api_calls_used >= self.state.max_per_project_calls:
                # Mark as complete with what we have
                actions.append(Action(
                    ActionType.COMPLETE_PROJECT,
                    target_id=project_id,
                    priority=10,
                ))
                continue
            
            # Gather missing facts in order
            if not project.ci_checked:
                actions.append(Action(
                    ActionType.DETECT_CI,
                    target_id=project_id,
                    target_path=project.path_with_namespace,
                    params={"ref": project.default_branch},
                    priority=3,
                ))
            elif not project.lfs_checked:
                actions.append(Action(
                    ActionType.DETECT_LFS,
                    target_id=project_id,
                    target_path=project.path_with_namespace,
                    params={"ref": project.default_branch},
                    priority=3,
                ))
            elif not project.mr_counts_fetched:
                actions.append(Action(
                    ActionType.GET_MR_COUNTS,
                    target_id=project_id,
                    target_path=project.path_with_namespace,
                    priority=4,
                ))
            elif not project.issue_counts_fetched:
                actions.append(Action(
                    ActionType.GET_ISSUE_COUNTS,
                    target_id=project_id,
                    target_path=project.path_with_namespace,
                    priority=4,
                ))
            else:
                # Project is complete
                actions.append(Action(
                    ActionType.COMPLETE_PROJECT,
                    target_id=project_id,
                    priority=10,
                ))
        
        # If no pending actions, we're done
        if not actions:
            return [Action(ActionType.DONE)]
        
        # Sort by priority and return
        actions.sort(key=lambda a: a.priority)
        return actions[:max_actions]


class AgentExecutor:
    """
    Executes actions and updates state.
    
    Handles the actual API calls and state transitions.
    """
    
    def __init__(self, state: AgentState, tools: GitLabTools):
        self.state = state
        self.tools = tools
    
    def execute(self, action: Action) -> bool:
        """
        Execute an action and update state.
        
        Args:
            action: Action to execute
            
        Returns:
            True if action was successful
        """
        logger.debug(f"Executing action: {action.action_type.name} on {action.target_path or action.target_id}")
        
        if action.action_type == ActionType.HEALTH_CHECK:
            return self._execute_health_check()
        elif action.action_type == ActionType.LIST_ALL_GROUPS:
            return self._execute_list_all_groups()
        elif action.action_type == ActionType.RESOLVE_GROUP:
            return self._execute_resolve_group(action.target_path)
        elif action.action_type == ActionType.RESOLVE_PROJECT:
            return self._execute_resolve_project(action.target_path)
        elif action.action_type == ActionType.LIST_SUBGROUPS:
            return self._execute_list_subgroups(action.target_id)
        elif action.action_type == ActionType.LIST_PROJECTS:
            return self._execute_list_projects(action.target_id)
        elif action.action_type == ActionType.DETECT_CI:
            return self._execute_detect_ci(action.target_id, action.params.get("ref"))
        elif action.action_type == ActionType.DETECT_LFS:
            return self._execute_detect_lfs(action.target_id, action.params.get("ref"))
        elif action.action_type == ActionType.GET_MR_COUNTS:
            return self._execute_get_mr_counts(action.target_id)
        elif action.action_type == ActionType.GET_ISSUE_COUNTS:
            return self._execute_get_issue_counts(action.target_id)
        elif action.action_type == ActionType.COMPLETE_PROJECT:
            return self._execute_complete_project(action.target_id)
        elif action.action_type == ActionType.DONE:
            return True
        
        logger.warning(f"Unknown action type: {action.action_type}")
        return False
    
    def _execute_health_check(self) -> bool:
        """Execute health check."""
        if not self.state.register_api_call():
            return False
        
        result = self.tools.health_check()
        self.state.health_checked = True
        
        if result.success and result.data.get("ok"):
            logger.info(f"Health check passed: {result.data.get('message')}")
            return True
        else:
            logger.error(f"Health check failed: {result.error or result.data.get('message')}")
            return False
    
    def _execute_resolve_group(self, group_path: str | None) -> bool:
        """Resolve group path to ID."""
        if not group_path:
            return False
        
        if not self.state.register_api_call():
            return False
        
        result = self.tools.resolve_group_id(group_path)
        
        if result.success and result.data:
            group_id = result.data
            self.state.root_group_id = group_id
            
            # Initialize group state
            group_state = GroupState(id=group_id, full_path=group_path)
            self.state.groups[group_id] = group_state
            self.state.pending_groups.append(group_id)
            
            logger.info(f"Resolved root group '{group_path}' to ID {group_id}")
            return True
        else:
            logger.error(f"Failed to resolve group '{group_path}': {result.error}")
            return False
    
    def _execute_resolve_project(self, project_path: str | None) -> bool:
        """Resolve project path and add it to pending projects for single-project mode."""
        if not project_path:
            return False
        
        if not self.state.register_api_call():
            return False
        
        # Use get_project with path (GitLab API supports project path)
        result = self.tools.get_project(project_path)
        
        if result.success and result.data:
            project_data = result.data
            project_id = project_data["id"]
            
            # Extract group from path (e.g., "group/subgroup/project" -> "group/subgroup")
            path_parts = project_data["path_with_namespace"].rsplit("/", 1)
            group_path = path_parts[0] if len(path_parts) > 1 else ""
            
            # Create project state
            project_state = ProjectState(
                id=project_id,
                path_with_namespace=project_data["path_with_namespace"],
                default_branch=project_data.get("default_branch"),
                archived=project_data.get("archived", False),
                visibility=project_data.get("visibility", "unknown"),
                group_id=0,  # Not used in single-project mode
                wiki_enabled=project_data.get("wiki_enabled", False),
            )
            
            self.state.projects[project_id] = project_state
            self.state.pending_projects.append(project_id)
            self.state.single_project_resolved = True
            
            logger.info(f"Resolved project '{project_path}' to ID {project_id}")
            return True
        else:
            logger.error(f"Failed to resolve project '{project_path}': {result.error}")
            return False
    
    def _execute_list_all_groups(self) -> bool:
        """List all accessible groups (for discover-all mode)."""
        if not self.state.register_api_call():
            return False
        
        result = self.tools.list_all_groups(top_level_only=True)
        
        if result.success:
            groups_found = result.data
            logger.info(f"Discovered {len(groups_found)} top-level groups")
            
            for group_info in groups_found:
                group_id = group_info["id"]
                group_path = group_info["full_path"]
                
                if group_id not in self.state.groups:
                    self.state.groups[group_id] = GroupState(
                        id=group_id,
                        full_path=group_path,
                    )
                    self.state.pending_groups.append(group_id)
            
            self.state.all_groups_listed = True
            return True
        else:
            logger.error(f"Failed to list all groups: {result.error}")
            return False
    
    def _execute_list_subgroups(self, group_id: int) -> bool:
        """List subgroups of a group."""
        if not self.state.register_api_call():
            return False
        
        result = self.tools.list_subgroups(group_id)
        group = self.state.groups.get(group_id)
        
        if group is None:
            return False
        
        group.subgroups_listed = True
        
        if result.success:
            for subgroup in result.data:
                subgroup_id = subgroup["id"]
                subgroup_path = subgroup["full_path"]
                
                # Add new group state
                if subgroup_id not in self.state.groups:
                    self.state.groups[subgroup_id] = GroupState(
                        id=subgroup_id,
                        full_path=subgroup_path,
                    )
                    self.state.pending_groups.append(subgroup_id)
                
                group.subgroup_ids.append(subgroup_id)
            
            logger.debug(f"Found {len(result.data)} subgroups in {group.full_path}")
            return True
        else:
            logger.error(f"Failed to list subgroups for {group.full_path}: {result.error}")
            return False
    
    def _execute_list_projects(self, group_id: int) -> bool:
        """List projects in a group."""
        if not self.state.register_api_call():
            return False
        
        result = self.tools.list_projects(group_id, include_subgroups=False)
        group = self.state.groups.get(group_id)
        
        if group is None:
            return False
        
        group.projects_listed = True
        
        if result.success:
            for project_data in result.data:
                project_id = project_data["id"]
                
                # Add new project state
                if project_id not in self.state.projects:
                    project_state = ProjectState(
                        id=project_id,
                        path_with_namespace=project_data["path_with_namespace"],
                        default_branch=project_data["default_branch"],
                        archived=project_data["archived"],
                        visibility=project_data["visibility"],
                        group_id=group_id,
                        details_fetched=True,  # Basic details already from list
                    )
                    self.state.projects[project_id] = project_state
                    self.state.pending_projects.append(project_id)
                
                group.project_ids.append(project_id)
            
            logger.debug(f"Found {len(result.data)} projects in {group.full_path}")
            
            # Check if group is complete
            if group.subgroups_listed and group.projects_listed:
                self._complete_group(group_id)
            
            return True
        else:
            logger.error(f"Failed to list projects for {group.full_path}: {result.error}")
            return False
    
    def _execute_detect_ci(self, project_id: int, ref: str | None) -> bool:
        """Detect CI configuration."""
        project = self.state.projects.get(project_id)
        if project is None:
            return False
        
        if not self.state.register_api_call(project_id):
            return False
        
        result = self.tools.detect_ci(project_id, ref)
        project.ci_checked = True
        
        if result.success:
            project.has_ci = result.data
            if result.data == "unknown" and result.error:
                project.add_error("detect_ci", result.error, result.status_code)
            return True
        else:
            project.has_ci = "unknown"
            project.add_error("detect_ci", result.error or "Unknown error", result.status_code)
            return False
    
    def _execute_detect_lfs(self, project_id: int, ref: str | None) -> bool:
        """Detect LFS usage."""
        project = self.state.projects.get(project_id)
        if project is None:
            return False
        
        if not self.state.register_api_call(project_id):
            return False
        
        result = self.tools.detect_lfs(project_id, ref)
        project.lfs_checked = True
        
        if result.success:
            project.has_lfs = result.data
            if result.data == "unknown" and result.error:
                project.add_error("detect_lfs", result.error, result.status_code)
            return True
        else:
            project.has_lfs = "unknown"
            project.add_error("detect_lfs", result.error or "Unknown error", result.status_code)
            return False
    
    def _execute_get_mr_counts(self, project_id: int) -> bool:
        """Get merge request counts."""
        project = self.state.projects.get(project_id)
        if project is None:
            return False
        
        # MR counts can use multiple API calls (one per state)
        if not self.state.register_api_call(project_id):
            return False
        
        result = self.tools.get_merge_request_counts(project_id, light_mode=True)
        project.mr_counts_fetched = True
        
        # Account for additional API calls (3 states)
        self.state.register_api_call(project_id)
        self.state.register_api_call(project_id)
        
        if result.success:
            project.mr_counts = result.data
            return True
        else:
            project.mr_counts = "unknown"
            project.add_error("get_mr_counts", result.error or "Unknown error", result.status_code)
            return False
    
    def _execute_get_issue_counts(self, project_id: int) -> bool:
        """Get issue counts."""
        project = self.state.projects.get(project_id)
        if project is None:
            return False
        
        if not self.state.register_api_call(project_id):
            return False
        
        result = self.tools.get_issue_counts(project_id, light_mode=True)
        project.issue_counts_fetched = True
        
        # Account for additional API calls (2 states)
        self.state.register_api_call(project_id)
        
        if result.success:
            project.issue_counts = result.data
            return True
        else:
            project.issue_counts = "unknown"
            project.add_error("get_issue_counts", result.error or "Unknown error", result.status_code)
            return False
    
    def _execute_complete_project(self, project_id: int) -> bool:
        """Mark project as complete and compute readiness."""
        project = self.state.projects.get(project_id)
        if project is None:
            return False
        
        # Remove from pending, add to completed
        if project_id in self.state.pending_projects:
            self.state.pending_projects.remove(project_id)
        self.state.completed_projects.add(project_id)
        
        logger.debug(f"Completed project: {project.path_with_namespace}")
        return True
    
    def _complete_group(self, group_id: int) -> None:
        """Mark group as complete."""
        if group_id in self.state.pending_groups:
            self.state.pending_groups.remove(group_id)
        self.state.completed_groups.add(group_id)
        
        group = self.state.groups.get(group_id)
        if group:
            logger.debug(f"Completed group: {group.full_path}")


def compute_project_readiness(project: ProjectState) -> dict[str, Any]:
    """
    Compute readiness assessment for a project.
    
    Args:
        project: Project state with discovered facts
        
    Returns:
        Readiness dictionary with complexity, blockers, notes
    """
    # Get MR and issue totals
    mr_total = 0
    if isinstance(project.mr_counts, dict):
        mr_total = project.mr_counts.get("total", 0)
        if isinstance(mr_total, str):
            mr_total = 1000  # Assume high if exceeded
    
    issue_total = 0
    if isinstance(project.issue_counts, dict):
        issue_total = project.issue_counts.get("total", 0)
        if isinstance(issue_total, str):
            issue_total = 1000
    
    complexity = estimate_complexity(
        has_ci=project.has_ci,
        has_lfs=project.has_lfs,
        mr_total=mr_total,
        issue_total=issue_total,
        archived=project.archived,
    )
    
    blockers = identify_blockers(
        has_ci=project.has_ci,
        has_lfs=project.has_lfs,
        visibility=project.visibility,
        errors=project.errors,
    )
    
    notes = generate_notes(
        archived=project.archived,
        default_branch=project.default_branch,
        mr_counts=project.mr_counts,
        issue_counts=project.issue_counts,
    )
    
    return {
        "complexity": complexity,
        "blockers": blockers,
        "notes": notes,
    }
