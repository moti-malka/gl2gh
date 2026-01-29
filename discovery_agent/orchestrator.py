"""
Orchestrator - Main discovery workflow controller.

Coordinates the agent, tools, and output generation.
Supports parallel processing for faster deep analysis.
Optionally uses Azure OpenAI for intelligent CI analysis.
"""

from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Any

from .agent_logic import (
    ActionType,
    AgentExecutor,
    AgentPlanner,
    AgentState,
    compute_project_readiness,
)
from .config import DiscoveryConfig, ensure_output_dir
from .gitlab_client import GitLabClient
from .schema import InventoryBuilder, validate_inventory
from .tools import GitLabTools
from .utils import now_iso, write_json, ProgressTracker
from .ci_parser import parse_ci_content, get_ci_complexity_score
from .scoring import calculate_migration_score, calculate_migration_hours, RepoProfile
from .enrichment_types import (
    calculate_risk_score,
    EnrichmentProfile,
    empty_integrations,
    empty_permissions,
    empty_risk_flags,
)
from .ai_analyzer import AIAnalyzer, create_ai_analyzer, AIAnalysisResult

logger = logging.getLogger(__name__)


class DiscoveryOrchestrator:
    """
    Orchestrates the discovery process.
    
    Manages the agent loop, tracks progress, and produces output.
    """
    
    def __init__(self, config: DiscoveryConfig):
        """
        Initialize the orchestrator.
        
        Args:
            config: Discovery configuration
        """
        self.config = config
        self.client: GitLabClient | None = None
        self.tools: GitLabTools | None = None
        self.state: AgentState | None = None
        self.inventory: InventoryBuilder | None = None
        self.progress: ProgressTracker = ProgressTracker()
        
        # Thread safety for parallel processing
        self._api_call_lock = Lock()
        
        # AI Analyzer for intelligent CI analysis
        self.ai_analyzer: AIAnalyzer | None = None
        self._ai_enabled = os.environ.get("ENABLE_AI_ANALYSIS", "").lower() in ("1", "true", "yes")
        
        # Timestamps
        self.started_at: str = ""
        self.finished_at: str = ""
    
    def run(self) -> dict[str, Any]:
        """
        Run the discovery process.
        
        Returns:
            Complete inventory dictionary
        """
        self.started_at = now_iso()
        if self.config.single_project_mode:
            logger.info(f"Starting discovery for project {self.config.project_path} at {self.config.gitlab_base_url}")
        elif self.config.root_group:
            logger.info(f"Starting discovery for group {self.config.root_group} at {self.config.gitlab_base_url}")
        else:
            logger.info(f"Starting discovery for ALL accessible groups at {self.config.gitlab_base_url}")
        logger.info(f"Budget: {self.config.max_api_calls} API calls, {self.config.max_per_project_calls} per project")
        
        try:
            # Initialize components
            self._initialize()
            
            # Run discovery loop
            self._run_discovery_loop()
            
            # Run deep analysis if enabled
            if self.config.deep:
                self._run_deep_analysis()
            
            # Build inventory
            inventory = self._build_inventory()
            
            # Validate and save
            self._save_inventory(inventory)
            
            return inventory
            
        finally:
            self._cleanup()
    
    def _initialize(self) -> None:
        """Initialize client, tools, and state."""
        # Create GitLab client
        self.client = GitLabClient(
            base_url=self.config.gitlab_base_url,
            token=self.config.gitlab_token,
            timeout=self.config.timeout,
            verify_ssl=self.config.verify_ssl,
        )
        
        # Create tools
        self.tools = GitLabTools(self.client)
        
        # Initialize agent state
        self.state = AgentState(
            root_group_path=self.config.root_group or "",
            max_api_calls=self.config.max_api_calls,
            max_per_project_calls=self.config.max_per_project_calls,
            discover_all_mode=self.config.discover_all,
            single_project_mode=self.config.single_project_mode,
            single_project_path=self.config.project_path or "",
        )
        
        # Initialize inventory builder
        self.inventory = InventoryBuilder()
        
        # Initialize AI analyzer if enabled
        if self._ai_enabled:
            self.ai_analyzer = create_ai_analyzer()
            if self.ai_analyzer and self.ai_analyzer.is_available:
                logger.info("🤖 AI-powered CI analysis enabled (Azure OpenAI)")
            else:
                logger.warning("AI analysis requested but Azure OpenAI not configured")
                self.ai_analyzer = None
        
        # Ensure output directory exists
        ensure_output_dir(self.config)
    
    def _run_discovery_loop(self) -> None:
        """Run the main discovery agent loop."""
        if not self.state or not self.tools:
            raise RuntimeError("Orchestrator not initialized")
        
        planner = AgentPlanner(self.state, self.tools)
        executor = AgentExecutor(self.state, self.tools)
        
        iteration = 0
        max_iterations = self.config.max_api_calls * 2  # Safety limit
        
        while iteration < max_iterations:
            iteration += 1
            
            # Get next actions
            actions = planner.get_next_actions(max_actions=1)
            
            if not actions:
                logger.info("No more actions to take")
                break
            
            action = actions[0]
            
            # Check for completion
            if action.action_type == ActionType.DONE:
                logger.info("Discovery complete")
                break
            
            # Execute action
            try:
                success = executor.execute(action)
                
                if not success:
                    logger.warning(f"Action failed: {action.action_type.name}")
                
                # Update progress tracking
                self._update_progress()
                
            except Exception as e:
                logger.error(f"Error executing action {action.action_type.name}: {e}")
                # Continue with next action
            
            # Check budget
            if self.state.is_budget_exceeded:
                logger.warning("API budget exceeded, stopping discovery")
                break
        
        if iteration >= max_iterations:
            logger.error("Maximum iterations exceeded, stopping discovery")
        
        logger.info(f"Discovery loop completed after {iteration} iterations")
        logger.info(f"Total API calls: {self.state.total_api_calls}")
    
    def _run_deep_analysis(self) -> None:
        """Run deep analysis on projects for migration scoring with parallel processing."""
        if not self.state or not self.tools:
            raise RuntimeError("Orchestrator not initialized")
        
        # Sort projects by RISK SCORE (higher = more priority for deep scan)
        projects_to_analyze = list(self.state.projects.values())
        
        def risk_sort_key(p):
            """Calculate risk score for prioritization."""
            return -calculate_risk_score(
                has_ci=p.has_ci,
                archived=p.archived,
                default_branch=p.default_branch,
                mr_counts=p.mr_counts,
                issue_counts=p.issue_counts,
            )
        
        projects_to_analyze.sort(key=risk_sort_key)
        
        # Limit if configured
        if self.config.deep_top_n > 0:
            projects_to_analyze = projects_to_analyze[:self.config.deep_top_n]
        
        total = len(projects_to_analyze)
        
        # Determine parallelism level from environment or use default
        # Default to 4 workers for balanced performance vs API rate limits
        max_workers = int(os.environ.get("DISCOVERY_PARALLEL_WORKERS", "4"))
        
        if max_workers > 1:
            logger.info(f"Starting parallel deep analysis on {total} projects with {max_workers} workers")
            self._run_parallel_analysis(projects_to_analyze, max_workers)
        else:
            logger.info(f"Starting sequential deep analysis on {total} projects")
            self._run_sequential_analysis(projects_to_analyze)
        
        logger.info("Deep analysis complete")
    
    def _run_sequential_analysis(self, projects) -> None:
        """Run deep analysis sequentially (original behavior)."""
        total = len(projects)
        for idx, project in enumerate(projects, 1):
            if self.state.is_budget_exceeded:
                logger.warning("Budget exceeded during deep analysis")
                break
            
            logger.info(f"[{idx}/{total}] Deep analysis: {project.path_with_namespace}")
            
            try:
                self._analyze_project_deep_v2(project)
            except Exception as e:
                logger.error(f"Error in deep analysis for {project.path_with_namespace}: {e}")
                project.errors.append({
                    "step": "deep_analysis",
                    "status": None,
                    "message": str(e),
                })
    
    def _run_parallel_analysis(self, projects, max_workers: int) -> None:
        """Run deep analysis in parallel using thread pool."""
        total = len(projects)
        completed = 0
        
        def analyze_one(idx_project):
            """Analyze a single project (runs in thread)."""
            idx, project = idx_project
            try:
                self._analyze_project_deep_v2_threadsafe(project)
                return (project, None)
            except Exception as e:
                return (project, e)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            futures = {
                executor.submit(analyze_one, (idx, proj)): proj 
                for idx, proj in enumerate(projects, 1)
            }
            
            # Process as they complete
            for future in as_completed(futures):
                if self.state.is_budget_exceeded:
                    logger.warning("Budget exceeded during parallel deep analysis")
                    # Cancel remaining futures
                    for f in futures:
                        f.cancel()
                    break
                
                project, error = future.result()
                completed += 1
                
                if error:
                    logger.error(f"Error in deep analysis for {project.path_with_namespace}: {error}")
                    project.errors.append({
                        "step": "deep_analysis",
                        "status": None,
                        "message": str(error),
                    })
                else:
                    if completed % 10 == 0 or completed == total:
                        logger.info(f"Deep analysis progress: {completed}/{total} projects")
    
    def _analyze_project_deep_v2_threadsafe(self, project) -> None:
        """
        Thread-safe version of _analyze_project_deep_v2.
        Uses locks for shared state (API call counter).
        """
        if not self.tools or not self.state:
            return
        
        project_id = project.id
        ref = project.default_branch
        
        # Initialize profiles
        permissions = empty_permissions()
        integrations = empty_integrations()
        risk_flags = empty_risk_flags()
        
        # Track API calls locally then update shared counter
        local_api_calls = 0
        
        def register_api_call():
            nonlocal local_api_calls
            local_api_calls += 1
            # Update shared state with lock
            with self._api_call_lock:
                self.state.register_api_call()
        
        # === Repository Profile ===
        repo_profile = RepoProfile(
            branches_count="unknown",
            tags_count="unknown",
            has_submodules="unknown",
            has_lfs=project.has_lfs if project.has_lfs != "unknown" else "unknown",
        )
        
        # Branches count
        result = self.tools.get_branches_count(project_id)
        register_api_call()
        if result.success:
            repo_profile["branches_count"] = result.data
            permissions["can_read_repo"] = True
        
        # Tags count
        result = self.tools.get_tags_count(project_id)
        register_api_call()
        if result.success:
            repo_profile["tags_count"] = result.data
            integrations["releases"]["tags_count"] = result.data
        
        # Submodules
        result = self.tools.detect_submodules(project_id, ref)
        register_api_call()
        if result.success:
            repo_profile["has_submodules"] = result.data
        
        # === CI Profile ===
        ci_profile = {
            "present": project.has_ci is True,
            "total_lines": 0,
            "features": {},
            "runner_hints": {},
        }
        
        ci_score = 0
        ci_factors = []
        ci_content_raw = ""  # Store raw content for AI analysis
        
        if project.has_ci is True:
            ci_result = self.tools.get_ci_content(project_id, ref, max_lines=400)
            register_api_call()
            
            if ci_result.success and ci_result.data:
                permissions["can_read_ci"] = True
                content = ci_result.data.get("content", "")
                ci_content_raw = content  # Save for AI analysis
                total_lines = ci_result.data.get("total_lines", 0)
                
                # Parse CI content
                parsed = parse_ci_content(content)
                ci_profile["total_lines"] = total_lines
                ci_profile["features"] = parsed.features
                ci_profile["runner_hints"] = parsed.runner_hints
                ci_profile["job_count"] = parsed.job_count
                ci_profile["include_count"] = parsed.include_count
                
                # Calculate CI complexity score
                ci_score, ci_factors = get_ci_complexity_score(parsed)
                
                # Set risk flags
                if ci_score > 30:
                    risk_flags["complex_ci"] = True
                if parsed.runner_hints.get("uses_tags") or parsed.runner_hints.get("possible_self_hosted"):
                    risk_flags["self_hosted_runner_hints"] = True
                
                # Detect Pages job
                if parsed.features.get("environments") or "pages" in content.lower():
                    integrations["pages"]["has_pages_job"] = True
        
        # === Integrations ===
        
        # Protected branches
        result = self.tools.get_protected_branches_count(project_id)
        register_api_call()
        if result.success:
            integrations["protected_branches"]["count"] = result.data
            if result.status_code != 403:
                permissions["can_read_protected_branches"] = True
        
        # CODEOWNERS
        result = self.tools.detect_codeowners(project_id, ref)
        register_api_call()
        if result.success:
            integrations["protected_branches"]["has_codeowners"] = result.data
        
        # CI Variables (project level)
        result = self.tools.get_project_variables_count(project_id)
        register_api_call()
        if result.success:
            integrations["variables"]["project_count"] = result.data
            if result.status_code != 403:
                permissions["can_read_variables"] = True
        
        # Webhooks
        result = self.tools.get_webhooks_count(project_id)
        register_api_call()
        if result.success:
            integrations["webhooks"]["count"] = result.data
            if result.status_code != 403:
                permissions["can_read_webhooks"] = True
        
        # Releases
        result = self.tools.get_releases_count(project_id)
        register_api_call()
        if result.success:
            integrations["releases"]["releases_count"] = result.data
        
        # Container files (registry hint)
        result = self.tools.detect_container_files(project_id, ref)
        register_api_call()
        if result.success and result.data:
            has_docker = result.data.get("has_dockerfile")
            if has_docker is True:
                integrations["registry"]["has_images"] = True
        
        # Public folder (Pages hint)
        result = self.tools.detect_public_folder(project_id, ref)
        register_api_call()
        if result.success:
            integrations["pages"]["has_public_folder"] = result.data
        
        # Project features (registry enabled, pages enabled)
        result = self.tools.get_project_features(project_id)
        register_api_call()
        if result.success and result.data:
            features = result.data
            integrations["registry"]["enabled"] = features.get("container_registry_enabled", False)
            pages_level = features.get("pages_access_level", "disabled")
            integrations["pages"]["enabled"] = pages_level != "disabled"
            
            # Store wiki_enabled for scoring
            project.wiki_enabled = features.get("wiki_enabled", False)
        
        # === Risk Flags ===
        mr_counts = project.mr_counts
        issue_counts = project.issue_counts
        
        if isinstance(mr_counts, dict):
            total = mr_counts.get("total", 0)
            if isinstance(total, str) and total.startswith(">"):
                risk_flags["exceeded_limits"] = True
            open_mrs = mr_counts.get("open", 0)
            if isinstance(open_mrs, int) and open_mrs > 20:
                risk_flags["big_mr_backlog"] = True
            elif isinstance(total, int) and total > 500:
                risk_flags["big_mr_backlog"] = True
        
        if isinstance(issue_counts, dict):
            total = issue_counts.get("total", 0)
            if isinstance(total, str) and total.startswith(">"):
                risk_flags["exceeded_limits"] = True
            open_issues = issue_counts.get("open", 0)
            if isinstance(open_issues, int) and open_issues > 100:
                risk_flags["big_issue_backlog"] = True
            elif isinstance(total, int) and total > 1000:
                risk_flags["big_issue_backlog"] = True
        
        if not project.default_branch:
            risk_flags["missing_default_branch"] = True
        
        # === Calculate Migration Estimate (v2) - Rule-based baseline ===
        estimate = calculate_migration_hours(
            repo_profile=repo_profile,
            ci_score=ci_score,
            ci_features=ci_profile.get("features"),
            runner_hints=ci_profile.get("runner_hints"),
            mr_counts=mr_counts,
            issue_counts=issue_counts,
            integrations=integrations,
            permissions=permissions,
            archived=project.archived,
        )
        
        # === AI-Powered FULL PROJECT Analysis (if enabled) ===
        ai_analysis = None
        if self.ai_analyzer:
            try:
                # Build comprehensive project data for AI
                project_data = {
                    "name": project.path_with_namespace,
                    "archived": project.archived,
                    "default_branch": project.default_branch,
                    "repo_profile": repo_profile,
                    "ci_content": ci_content_raw if ci_content_raw else "",
                    "ci_profile": ci_profile,
                    "issue_counts": issue_counts,
                    "mr_counts": mr_counts,
                    "integrations": integrations,
                }
                
                ai_analysis = self.ai_analyzer.analyze_full_project(project_data)
                
                if ai_analysis:
                    # Use simple AI estimate
                    ai_hours_low = ai_analysis["hours_low"]
                    ai_hours_high = ai_analysis["hours_high"]
                    
                    # Replace rule-based estimate with AI estimate
                    estimate["hours_low"] = round(ai_hours_low, 1)
                    estimate["hours_high"] = round(ai_hours_high, 1)
                    
                    # Update confidence based on risk
                    risk = ai_analysis.get("risk", "medium")
                    estimate["confidence"] = "high" if risk == "low" else "medium" if risk == "medium" else "low"
                    
                    # Use not_supported as blockers (critical items)
                    if ai_analysis.get("not_supported"):
                        estimate["blockers"] = ai_analysis["not_supported"][:3]
                    
                    # Use supported as drivers
                    if ai_analysis.get("supported"):
                        estimate["drivers"] = ai_analysis["supported"][:5]
                    
                    # Add breakdown and critical_notes
                    if ai_analysis.get("breakdown"):
                        estimate["breakdown"] = ai_analysis["breakdown"]
                    
                    if ai_analysis.get("critical_notes"):
                        estimate["critical_notes"] = ai_analysis["critical_notes"]
                    
                    # Store simple AI analysis
                    ci_profile["ai_analysis"] = {
                        "hours_low": ai_hours_low,
                        "hours_high": ai_hours_high,
                        "risk": risk,
                        "supported": ai_analysis.get("supported", []),
                        "not_supported": ai_analysis.get("not_supported", []),
                    }
                    
                    # Log detailed summary
                    not_supported_str = ""
                    if ai_analysis.get("not_supported"):
                        not_supported_str = f" ⚠️ {', '.join(ai_analysis['not_supported'][:2])}"
                    
                    breakdown_str = ""
                    if ai_analysis.get("breakdown"):
                        b = ai_analysis["breakdown"]
                        breakdown_str = (
                            f" [Code: {b.get('code', {}).get('hours_low', 0)}-{b.get('code', {}).get('hours_high', 0)}h, "
                            f"MRs: {b.get('mrs', {}).get('hours_low', 0)}-{b.get('mrs', {}).get('hours_high', 0)}h, "
                            f"Issues: {b.get('issues', {}).get('hours_low', 0)}-{b.get('issues', {}).get('hours_high', 0)}h, "
                            f"CI: {b.get('ci', {}).get('hours_low', 0)}-{b.get('ci', {}).get('hours_high', 0)}h]"
                        )
                    
                    logger.info(
                        f"  🤖 {project.path_with_namespace}: "
                        f"{ai_hours_low}-{ai_hours_high}h (risk: {risk}){not_supported_str}{breakdown_str}"
                    )
                        
            except Exception as e:
                logger.warning(f"AI analysis failed for {project.path_with_namespace}: {e}")
        
        # === Store Results on Project (thread-safe - each project is independent) ===
        project.repo_profile = repo_profile
        project.ci_profile = ci_profile
        project.enrichment = EnrichmentProfile(
            permissions=permissions,
            integrations=integrations,
            risk_flags=risk_flags,
        )
        project.estimate = estimate
        
        # Legacy v1 compat
        project.migration_estimate = {
            "work_score": estimate["work_score"],
            "bucket": estimate["bucket"],
            "drivers": estimate["drivers"],
        }
        
        logger.debug(
            f"  {project.path_with_namespace}: "
            f"hours={estimate['hours_low']}-{estimate['hours_high']}h, "
            f"confidence={estimate['confidence']}"
        )
    
    def _analyze_project_deep_v2(self, project) -> None:
        """
        Perform deep v2 analysis on a single project.
        
        Collects all enrichment data for accurate pricing:
        - Repository profile (branches, tags, submodules, LFS)
        - CI profile (features, runner hints)
        - Integrations (protected branches, variables, webhooks, registry, pages, releases)
        - Permissions footprint
        - Risk flags
        """
        if not self.tools or not self.state:
            return
        
        project_id = project.id
        ref = project.default_branch
        
        # Initialize profiles
        permissions = empty_permissions()
        integrations = empty_integrations()
        risk_flags = empty_risk_flags()
        
        # === Repository Profile ===
        repo_profile = RepoProfile(
            branches_count="unknown",
            tags_count="unknown",
            has_submodules="unknown",
            has_lfs=project.has_lfs if project.has_lfs != "unknown" else "unknown",
        )
        
        # Branches count
        result = self.tools.get_branches_count(project_id)
        self.state.register_api_call()
        if result.success:
            repo_profile["branches_count"] = result.data
            permissions["can_read_repo"] = True
        
        # Tags count
        result = self.tools.get_tags_count(project_id)
        self.state.register_api_call()
        if result.success:
            repo_profile["tags_count"] = result.data
            integrations["releases"]["tags_count"] = result.data
        
        # Submodules
        result = self.tools.detect_submodules(project_id, ref)
        self.state.register_api_call()
        if result.success:
            repo_profile["has_submodules"] = result.data
        
        # === CI Profile ===
        ci_profile = {
            "present": project.has_ci is True,
            "total_lines": 0,
            "features": {},
            "runner_hints": {},
        }
        
        ci_score = 0
        ci_factors = []
        
        if project.has_ci is True:
            ci_result = self.tools.get_ci_content(project_id, ref, max_lines=400)
            self.state.register_api_call()
            
            if ci_result.success and ci_result.data:
                permissions["can_read_ci"] = True
                content = ci_result.data.get("content", "")
                total_lines = ci_result.data.get("total_lines", 0)
                
                # Parse CI content
                parsed = parse_ci_content(content)
                ci_profile["total_lines"] = total_lines
                ci_profile["features"] = parsed.features
                ci_profile["runner_hints"] = parsed.runner_hints
                ci_profile["job_count"] = parsed.job_count
                ci_profile["include_count"] = parsed.include_count
                
                # Calculate CI complexity score
                ci_score, ci_factors = get_ci_complexity_score(parsed)
                
                # Set risk flags
                if ci_score > 30:
                    risk_flags["complex_ci"] = True
                if parsed.runner_hints.get("uses_tags") or parsed.runner_hints.get("possible_self_hosted"):
                    risk_flags["self_hosted_runner_hints"] = True
                
                # Detect Pages job
                if parsed.features.get("environments") or "pages" in content.lower():
                    integrations["pages"]["has_pages_job"] = True
        
        # === Integrations ===
        
        # Protected branches
        result = self.tools.get_protected_branches_count(project_id)
        self.state.register_api_call()
        if result.success:
            integrations["protected_branches"]["count"] = result.data
            if result.status_code != 403:
                permissions["can_read_protected_branches"] = True
        
        # CODEOWNERS
        result = self.tools.detect_codeowners(project_id, ref)
        self.state.register_api_call()
        if result.success:
            integrations["protected_branches"]["has_codeowners"] = result.data
        
        # CI Variables (project level)
        result = self.tools.get_project_variables_count(project_id)
        self.state.register_api_call()
        if result.success:
            integrations["variables"]["project_count"] = result.data
            if result.status_code != 403:
                permissions["can_read_variables"] = True
        
        # Webhooks
        result = self.tools.get_webhooks_count(project_id)
        self.state.register_api_call()
        if result.success:
            integrations["webhooks"]["count"] = result.data
            if result.status_code != 403:
                permissions["can_read_webhooks"] = True
        
        # Releases
        result = self.tools.get_releases_count(project_id)
        self.state.register_api_call()
        if result.success:
            integrations["releases"]["releases_count"] = result.data
        
        # Container files (registry hint)
        result = self.tools.detect_container_files(project_id, ref)
        self.state.register_api_call()
        if result.success and result.data:
            has_docker = result.data.get("has_dockerfile")
            if has_docker is True:
                integrations["registry"]["has_images"] = True
        
        # Public folder (Pages hint)
        result = self.tools.detect_public_folder(project_id, ref)
        self.state.register_api_call()
        if result.success:
            integrations["pages"]["has_public_folder"] = result.data
        
        # Project features (registry enabled, pages enabled)
        result = self.tools.get_project_features(project_id)
        self.state.register_api_call()
        if result.success and result.data:
            features = result.data
            integrations["registry"]["enabled"] = features.get("container_registry_enabled", False)
            pages_level = features.get("pages_access_level", "disabled")
            integrations["pages"]["enabled"] = pages_level != "disabled"
            
            # Store wiki_enabled for scoring
            project.wiki_enabled = features.get("wiki_enabled", False)
        
        # === Risk Flags ===
        
        # Check for exceeded limits
        mr_counts = project.mr_counts
        issue_counts = project.issue_counts
        
        if isinstance(mr_counts, dict):
            total = mr_counts.get("total", 0)
            if isinstance(total, str) and total.startswith(">"):
                risk_flags["exceeded_limits"] = True
            open_mrs = mr_counts.get("open", 0)
            if isinstance(open_mrs, int) and open_mrs > 20:
                risk_flags["big_mr_backlog"] = True
            elif isinstance(total, int) and total > 500:
                risk_flags["big_mr_backlog"] = True
        
        if isinstance(issue_counts, dict):
            total = issue_counts.get("total", 0)
            if isinstance(total, str) and total.startswith(">"):
                risk_flags["exceeded_limits"] = True
            open_issues = issue_counts.get("open", 0)
            if isinstance(open_issues, int) and open_issues > 100:
                risk_flags["big_issue_backlog"] = True
            elif isinstance(total, int) and total > 1000:
                risk_flags["big_issue_backlog"] = True
        
        if not project.default_branch:
            risk_flags["missing_default_branch"] = True
        
        # === Calculate Migration Estimate (v2) ===
        estimate = calculate_migration_hours(
            repo_profile=repo_profile,
            ci_score=ci_score,
            ci_features=ci_profile.get("features"),
            runner_hints=ci_profile.get("runner_hints"),
            mr_counts=mr_counts,
            issue_counts=issue_counts,
            integrations=integrations,
            permissions=permissions,
            archived=project.archived,
        )
        
        # === Store Results on Project ===
        project.repo_profile = repo_profile
        project.ci_profile = ci_profile
        project.enrichment = EnrichmentProfile(
            permissions=permissions,
            integrations=integrations,
            risk_flags=risk_flags,
        )
        project.estimate = estimate
        
        # Legacy v1 compat
        project.migration_estimate = {
            "work_score": estimate["work_score"],
            "bucket": estimate["bucket"],
            "drivers": estimate["drivers"],
        }
        
        logger.debug(
            f"  {project.path_with_namespace}: "
            f"hours={estimate['hours_low']}-{estimate['hours_high']}h, "
            f"confidence={estimate['confidence']}"
        )
    
    def _analyze_project_deep(self, project) -> None:
        """Legacy deep analysis - redirects to v2."""
        self._analyze_project_deep_v2(project)
    
    def _update_progress(self) -> None:
        """Update progress tracking."""
        if not self.state:
            return
        
        self.progress.set_totals(
            groups=len(self.state.groups),
            projects=len(self.state.projects),
        )
        self.progress.completed_groups = len(self.state.completed_groups)
        self.progress.completed_projects = len(self.state.completed_projects)
    
    def _build_inventory(self) -> dict[str, Any]:
        """Build the final inventory from state."""
        if not self.state or not self.inventory:
            raise RuntimeError("Orchestrator not initialized")
        
        self.finished_at = now_iso()
        
        # Add groups
        for group_id, group in sorted(self.state.groups.items(), key=lambda x: x[1].full_path):
            self.inventory.add_group(group_id, group.full_path)
            for project_id in group.project_ids:
                self.inventory.add_project_to_group(group_id, project_id)
        
        # Add projects with facts and readiness
        for project_id, project in sorted(
            self.state.projects.items(),
            key=lambda x: x[1].path_with_namespace,
        ):
            # Compute readiness
            readiness = compute_project_readiness(project)
            
            # Build facts
            facts = {
                "has_ci": project.has_ci,
                "has_lfs": project.has_lfs,
                "mr_counts": project.mr_counts,
                "issue_counts": project.issue_counts,
            }
            
            # Add deep analysis data if present (v1 compat)
            if hasattr(project, 'repo_profile') and project.repo_profile:
                facts["repo_profile"] = project.repo_profile
            if hasattr(project, 'ci_profile') and project.ci_profile:
                facts["ci_profile"] = project.ci_profile
            if hasattr(project, 'migration_estimate') and project.migration_estimate:
                facts["migration_estimate"] = project.migration_estimate
            
            # Add v2 enrichment data
            if hasattr(project, 'enrichment') and project.enrichment:
                facts["enrichment"] = project.enrichment.to_dict()
            
            # Add v2 estimate (separate from facts for clarity)
            estimate_data = None
            if hasattr(project, 'estimate') and project.estimate:
                estimate_data = {
                    "hours_low": project.estimate.get("hours_low"),
                    "hours_high": project.estimate.get("hours_high"),
                    "confidence": project.estimate.get("confidence"),
                    "drivers": project.estimate.get("drivers"),
                    "unknowns": project.estimate.get("unknowns"),
                    "blockers": project.estimate.get("blockers"),
                    "scope_flags": project.estimate.get("scope_flags"),
                    # AI breakdown data
                    "breakdown": project.estimate.get("breakdown"),
                    "critical_notes": project.estimate.get("critical_notes"),
                }
            
            self.inventory.add_project(
                project_id=project.id,
                path_with_namespace=project.path_with_namespace,
                default_branch=project.default_branch,
                archived=project.archived,
                visibility=project.visibility,
                facts=facts,
                readiness=readiness,
                errors=project.errors,
                estimate=estimate_data,
            )
        
        # Determine the target description for inventory
        if self.config.single_project_mode:
            target_desc = f"PROJECT:{self.config.project_path}"
        elif self.config.root_group:
            target_desc = self.config.root_group
        else:
            target_desc = "ALL_ACCESSIBLE_GROUPS"
        
        # Build final inventory
        return self.inventory.build(
            started_at=self.started_at,
            finished_at=self.finished_at,
            base_url=self.config.gitlab_base_url,
            root_group=target_desc,
            api_calls=self.state.total_api_calls,
        )
    
    def _save_inventory(self, inventory: dict[str, Any]) -> None:
        """Save inventory to file and validate."""
        # Validate
        is_valid, errors = validate_inventory(inventory)
        
        if not is_valid:
            logger.warning(f"Inventory validation errors: {errors}")
        else:
            logger.info("Inventory validated successfully")
        
        # Save main inventory
        output_path = Path(self.config.output_dir)
        inventory_path = output_path / "inventory.json"
        write_json(inventory_path, inventory)
        logger.info(f"Inventory saved to {inventory_path}")
        
        # Save summary
        summary = self._generate_summary(inventory)
        summary_path = output_path / "summary.txt"
        summary_path.write_text(summary, encoding="utf-8")
        logger.info(f"Summary saved to {summary_path}")
        
        # Print summary
        print("\n" + "=" * 60)
        print(summary)
        print("=" * 60)
    
    def _generate_summary(self, inventory: dict[str, Any]) -> str:
        """Generate human-readable summary."""
        stats = inventory["run"]["stats"]
        projects = inventory["projects"]
        
        # Count by complexity
        complexity_counts = {"low": 0, "medium": 0, "high": 0}
        for p in projects:
            complexity = p["readiness"]["complexity"]
            complexity_counts[complexity] = complexity_counts.get(complexity, 0) + 1
        
        # Count projects with blockers
        with_blockers = sum(1 for p in projects if p["readiness"]["blockers"])
        
        # Count projects with CI
        with_ci = sum(1 for p in projects if p["facts"]["has_ci"] is True)
        
        # Count projects with LFS
        with_lfs = sum(1 for p in projects if p["facts"]["has_lfs"] is True)
        
        # Count archived
        archived = sum(1 for p in projects if p["archived"])
        
        lines = [
            "DISCOVERY SUMMARY",
            f"Base URL: {inventory['run']['base_url']}",
            f"Root Group: {inventory['run']['root_group']}",
            f"Started: {inventory['run']['started_at']}",
            f"Finished: {inventory['run']['finished_at']}",
            "",
            "STATISTICS",
            f"  Groups: {stats['groups']}",
            f"  Projects: {stats['projects']}",
            f"  API Calls: {stats['api_calls']}",
            f"  Errors: {stats['errors']}",
            "",
            "PROJECT BREAKDOWN",
            f"  Complexity - Low: {complexity_counts['low']}, Medium: {complexity_counts['medium']}, High: {complexity_counts['high']}",
            f"  With CI/CD: {with_ci}",
            f"  With LFS: {with_lfs}",
            f"  Archived: {archived}",
            f"  With Blockers: {with_blockers}",
        ]
        
        # v2 estimate summary
        with_estimates = [p for p in projects if p.get("estimate")]
        if with_estimates:
            total_hours_low = sum(p["estimate"]["hours_low"] for p in with_estimates)
            total_hours_high = sum(p["estimate"]["hours_high"] for p in with_estimates)
            
            confidence_counts = {"high": 0, "medium": 0, "low": 0}
            for p in with_estimates:
                conf = p["estimate"]["confidence"]
                confidence_counts[conf] = confidence_counts.get(conf, 0) + 1
            
            lines.extend([
                "",
                "HOURS ESTIMATES (v2)",
                f"  Projects with estimates: {len(with_estimates)}",
                f"  Total Hours (range): {total_hours_low:.1f}h - {total_hours_high:.1f}h",
                f"  Confidence - High: {confidence_counts['high']}, Medium: {confidence_counts['medium']}, Low: {confidence_counts['low']}",
            ])
            
            # Top 5 highest-effort projects by hours_high
            sorted_by_hours = sorted(
                with_estimates,
                key=lambda p: p["estimate"]["hours_high"],
                reverse=True,
            )[:5]
            
            if sorted_by_hours:
                lines.append("")
                lines.append("  Top 5 Highest Effort (by hours):")
                for p in sorted_by_hours:
                    est = p["estimate"]
                    lines.append(
                        f"    - {p['path_with_namespace']}: "
                        f"{est['hours_low']}-{est['hours_high']}h "
                        f"(confidence: {est['confidence']})"
                    )
            
            # Collect all blockers
            all_blockers = []
            for p in with_estimates:
                for b in p["estimate"].get("blockers", []):
                    if b not in all_blockers:
                        all_blockers.append(b)
            
            if all_blockers:
                lines.append("")
                lines.append("  Common Blockers:")
                for b in all_blockers[:5]:
                    lines.append(f"    ⚠️  {b}")
        
        # Add legacy deep analysis summary if present (backward compat)
        deep_analyzed = [p for p in projects if "migration_estimate" in p["facts"]]
        if deep_analyzed and not with_estimates:
            bucket_counts = {"S": 0, "M": 0, "L": 0, "XL": 0}
            total_score = 0
            for p in deep_analyzed:
                bucket = p["facts"]["migration_estimate"]["bucket"]
                bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
                total_score += p["facts"]["migration_estimate"]["work_score"]
            
            avg_score = total_score / len(deep_analyzed) if deep_analyzed else 0
            
            lines.extend([
                "",
                "DEEP ANALYSIS (legacy)",
                f"  Projects Analyzed: {len(deep_analyzed)}",
                f"  Average Work Score: {avg_score:.1f}/100",
                f"  Buckets - S: {bucket_counts['S']}, M: {bucket_counts['M']}, L: {bucket_counts['L']}, XL: {bucket_counts['XL']}",
            ])
        
        lines.extend([
            "",
            f"Output: {Path(self.config.output_dir) / 'inventory.json'}",
        ])
        
        return "\n".join(lines)
    
    def _cleanup(self) -> None:
        """Cleanup resources."""
        if self.client:
            self.client.close()
            self.client = None


def run_discovery(config: DiscoveryConfig) -> dict[str, Any]:
    """
    Convenience function to run discovery.
    
    Args:
        config: Discovery configuration
        
    Returns:
        Complete inventory dictionary
    """
    orchestrator = DiscoveryOrchestrator(config)
    return orchestrator.run()
