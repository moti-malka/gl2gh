"""Discovery Agent - GitLab project discovery and analysis using Microsoft Agent Framework"""

from typing import Any, Dict, List, Optional
import json
import os
from pathlib import Path
from datetime import datetime
from app.agents.base_agent import BaseAgent, AgentResult
from app.clients.gitlab_client import GitLabClient
from app.utils.logging import get_logger

logger = get_logger(__name__)


class DiscoveryAgent(BaseAgent):
    """
    Discovery Agent for GitLab project scanning and readiness assessment.
    
    This agent uses Microsoft Agent Framework patterns to:
    - Scan GitLab groups and projects
    - Build comprehensive inventory
    - Assess migration readiness
    - Generate detailed reports
    
    Following MAF principles:
    - Clear input/output contracts
    - Deterministic behavior
    - Context awareness
    - Tool integration (GitLab API)
    - Robust error handling
    """
    
    def __init__(self):
        super().__init__(
            agent_name="DiscoveryAgent",
            instructions="""
            You are a specialized agent for discovering and analyzing GitLab projects.
            Your role is to:
            1. Scan GitLab groups and projects comprehensively
            2. Collect detailed facts about each project (CI, LFS, issues, MRs, etc.)
            3. Assess migration readiness and complexity
            4. Identify potential blockers
            5. Generate inventory and readiness reports
            
            Operate in read-only mode - make no changes to GitLab.
            Respect API rate limits and budgets.
            Handle errors gracefully and report partial results.
            """
        )
    
    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        """
        Validate discovery agent inputs.
        
        Required inputs:
            - gitlab_url: GitLab instance URL
            - gitlab_token: Personal Access Token
            - output_dir: Directory for artifacts
            
        Optional inputs:
            - root_group: Root group to scan (None = scan all accessible)
            - max_api_calls: API budget
            - max_per_project_calls: Per-project API budget
            - deep: Enable deep analysis
            - deep_top_n: Limit deep analysis to top N projects
        """
        required_fields = ["gitlab_url", "gitlab_token", "output_dir"]
        
        for field in required_fields:
            if field not in inputs:
                self.log_event("ERROR", f"Missing required input: {field}")
                return False
        
        # Validate URL format
        gitlab_url = inputs["gitlab_url"]
        if not (gitlab_url.startswith("http://") or gitlab_url.startswith("https://")):
            self.log_event("ERROR", f"Invalid GitLab URL format: {gitlab_url}")
            return False
        
        # Validate token format (basic check)
        gitlab_token = inputs["gitlab_token"]
        if not gitlab_token or len(gitlab_token) < 10:
            self.log_event("ERROR", "Invalid GitLab token")
            return False
        
        return True
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute discovery process.
        
        Detects all 14 component types for each project:
        1. Repository (branches, tags, commits)
        2. CI/CD (.gitlab-ci.yml)
        3. Issues
        4. Merge Requests
        5. Wiki
        6. Releases
        7. Packages
        8. Webhooks
        9. Schedules
        10. LFS
        11. Environments
        12. Protected branches/tags
        13. Deploy keys
        14. Project variables
        """
        self.log_event("INFO", "Starting GitLab discovery")
        
        try:
            # Update context
            self.update_context("run_started", True)
            self.update_context("gitlab_url", inputs["gitlab_url"])
            self.update_context("output_dir", inputs["output_dir"])
            
            # Create output directory
            output_dir = Path(inputs["output_dir"])
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize GitLab client with async context manager
            async with GitLabClient(inputs["gitlab_url"], inputs["gitlab_token"]) as client:
                # Discover projects using async methods
                projects_data = await self._discover_projects(client, inputs)
                
                # Generate enhanced outputs
                inventory = self._generate_inventory(projects_data, inputs)
                coverage = self._generate_coverage(projects_data)
                readiness = self._generate_readiness(projects_data)
                
                # Save artifacts
                artifacts = {}
                
                inventory_path = output_dir / "inventory.json"
                with open(inventory_path, 'w') as f:
                    json.dump(inventory, f, indent=2)
                artifacts["inventory"] = str(inventory_path)
                
                coverage_path = output_dir / "coverage.json"
                with open(coverage_path, 'w') as f:
                    json.dump(coverage, f, indent=2)
                artifacts["coverage"] = str(coverage_path)
                
                readiness_path = output_dir / "readiness.json"
                with open(readiness_path, 'w') as f:
                    json.dump(readiness, f, indent=2)
                artifacts["readiness"] = str(readiness_path)
                
                # Generate summary
                summary = self._generate_summary(projects_data)
                summary_path = output_dir / "summary.txt"
                with open(summary_path, 'w') as f:
                    f.write(summary)
                artifacts["summary"] = str(summary_path)
            
            stats = {
                "projects": len(projects_data),
                "groups": 0,  # Can be enhanced to scan groups
                "errors": sum(1 for p in projects_data if p.get("errors"))
            }
            
            self.log_event("INFO", "Discovery completed successfully", stats)
            
            return AgentResult(
                status="success",
                outputs={
                    "inventory": inventory,
                    "coverage": coverage,
                    "readiness": readiness,
                    "stats": stats,
                    "discovered_projects": projects_data
                },
                artifacts=list(artifacts.values()),
                errors=[]
            ).to_dict()
            
        except Exception as e:
            self.log_event("ERROR", f"Discovery failed: {str(e)}")
            return AgentResult(
                status="failed",
                outputs={},
                artifacts=[],
                errors=[{"step": "discovery", "message": str(e)}]
            ).to_dict()
    
    async def _discover_projects(self, client: GitLabClient, inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Discover all projects and detect components.
        
        Args:
            client: GitLab client
            inputs: Discovery configuration
            
        Returns:
            List of project data with detected components
        """
        discovered_projects = []
        
        # Get projects
        try:
            if inputs.get("root_group"):
                # Scan specific group
                group_id = inputs["root_group"]
                projects = await client.list_group_projects(group_id)
                self.log_event("INFO", f"Found {len(projects)} projects in group {group_id}")
            else:
                # Scan all accessible projects
                projects = await client.list_projects()
                self.log_event("INFO", f"Found {len(projects)} accessible projects")
        except Exception as e:
            self.log_event("ERROR", f"Failed to list projects: {str(e)}")
            return []
        
        # Detect components for each project
        for project in projects:
            try:
                project_data = await self._detect_project_components(client, project)
                discovered_projects.append(project_data)
                
                self.log_event("INFO", f"Scanned project: {project_data['path_with_namespace']}")
            except Exception as e:
                self.log_event("ERROR", f"Error scanning project {project.get('id')}: {str(e)}")
                discovered_projects.append({
                    "id": project.get("id"),
                    "name": project.get("name"),
                    "path_with_namespace": project.get("path_with_namespace"),
                    "errors": [str(e)],
                    "components": {}
                })
        
        return discovered_projects
    
    async def _detect_project_components(self, client: GitLabClient, project: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect all 14 component types for a project.
        
        Args:
            client: GitLab client
            project: Project metadata from GitLab API
            
        Returns:
            Project data with detected components
        """
        project_id = project["id"]
        
        # Basic project info
        project_data = {
            "id": project_id,
            "name": project["name"],
            "path_with_namespace": project["path_with_namespace"],
            "description": project.get("description"),
            "visibility": project.get("visibility"),
            "archived": project.get("archived", False),
            "created_at": project.get("created_at"),
            "last_activity_at": project.get("last_activity_at"),
            "web_url": project.get("web_url"),
            "default_branch": project.get("default_branch"),
        }
        
        # Component detection
        components = {}
        
        try:
            # 1. Repository (branches, tags, commits)
            branches = await client.list_branches(project_id)
            tags = await client.list_tags(project_id)
            commits = await client.get_commits(project_id, max_pages=1) if branches else []
            
            components["repository"] = {
                "enabled": True,
                "branches_count": len(branches),
                "tags_count": len(tags),
                "default_branch": project.get("default_branch"),
                "has_content": len(branches) > 0
            }
        except Exception as e:
            components["repository"] = {"enabled": False, "error": str(e)}
        
        try:
            # 2. CI/CD
            has_ci = await client.has_ci_config(project_id)
            pipelines = await client.list_pipelines(project_id, max_pages=1) if has_ci else []
            
            components["ci_cd"] = {
                "enabled": has_ci,
                "has_gitlab_ci": has_ci,
                "recent_pipelines": len(pipelines)
            }
        except Exception as e:
            components["ci_cd"] = {"enabled": False, "error": str(e)}
        
        try:
            # 3. Issues
            issues = await client.list_issues(project_id, state="opened")
            components["issues"] = {
                "enabled": True,
                "opened_count": len(issues),
                "has_issues": len(issues) > 0
            }
        except Exception as e:
            components["issues"] = {"enabled": False, "error": str(e)}
        
        try:
            # 4. Merge Requests
            mrs = await client.list_merge_requests(project_id, state="opened")
            components["merge_requests"] = {
                "enabled": True,
                "opened_count": len(mrs),
                "has_mrs": len(mrs) > 0
            }
        except Exception as e:
            components["merge_requests"] = {"enabled": False, "error": str(e)}
        
        try:
            # 5. Wiki
            has_wiki = await client.has_wiki(project_id)
            wiki_pages = await client.get_wiki_pages(project_id) if has_wiki else []
            
            components["wiki"] = {
                "enabled": has_wiki,
                "pages_count": len(wiki_pages)
            }
        except Exception as e:
            components["wiki"] = {"enabled": False, "error": str(e)}
        
        try:
            # 6. Releases
            releases = await client.list_releases(project_id)
            components["releases"] = {
                "enabled": True,
                "count": len(releases),
                "has_releases": len(releases) > 0
            }
        except Exception as e:
            components["releases"] = {"enabled": False, "error": str(e)}
        
        try:
            # 7. Packages/Registry
            has_packages = await client.has_packages(project_id)
            packages = await client.list_packages(project_id) if has_packages else []
            
            components["packages"] = {
                "enabled": has_packages,
                "count": len(packages),
                "has_packages": len(packages) > 0
            }
        except Exception as e:
            components["packages"] = {"enabled": False, "error": str(e)}
        
        try:
            # 8. Webhooks
            hooks = await client.list_hooks(project_id)
            components["webhooks"] = {
                "enabled": True,
                "count": len(hooks),
                "has_webhooks": len(hooks) > 0
            }
        except Exception as e:
            components["webhooks"] = {"enabled": False, "error": str(e)}
        
        try:
            # 9. Schedules
            schedules = await client.list_pipeline_schedules(project_id)
            components["schedules"] = {
                "enabled": True,
                "count": len(schedules),
                "has_schedules": len(schedules) > 0
            }
        except Exception as e:
            components["schedules"] = {"enabled": False, "error": str(e)}
        
        try:
            # 10. LFS
            has_lfs = await client.has_lfs(project_id)
            components["lfs"] = {
                "enabled": has_lfs,
                "detected": has_lfs
            }
        except Exception as e:
            components["lfs"] = {"enabled": False, "error": str(e)}
        
        try:
            # 11. Environments
            environments = await client.list_environments(project_id)
            components["environments"] = {
                "enabled": True,
                "count": len(environments),
                "has_environments": len(environments) > 0
            }
        except Exception as e:
            components["environments"] = {"enabled": False, "error": str(e)}
        
        try:
            # 12. Protected branches/tags
            protected_branches = await client.list_protected_branches(project_id)
            protected_tags = await client.list_protected_tags(project_id)
            
            components["protected_resources"] = {
                "enabled": True,
                "protected_branches_count": len(protected_branches),
                "protected_tags_count": len(protected_tags),
                "has_protections": len(protected_branches) > 0 or len(protected_tags) > 0
            }
        except Exception as e:
            components["protected_resources"] = {"enabled": False, "error": str(e)}
        
        try:
            # 13. Deploy keys
            deploy_keys = await client.list_deploy_keys(project_id)
            components["deploy_keys"] = {
                "enabled": True,
                "count": len(deploy_keys),
                "has_deploy_keys": len(deploy_keys) > 0
            }
        except Exception as e:
            components["deploy_keys"] = {"enabled": False, "error": str(e)}
        
        try:
            # 14. Project variables
            variables = await client.list_variables(project_id)
            components["variables"] = {
                "enabled": True,
                "count": len(variables),
                "has_variables": len(variables) > 0
            }
        except Exception as e:
            components["variables"] = {"enabled": False, "error": str(e)}
        
        project_data["components"] = components
        return project_data
    
    def _generate_inventory(self, projects_data: List[Dict[str, Any]], inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Generate inventory.json with all project data"""
        return {
            "version": "2.0",
            "generated_at": datetime.utcnow().isoformat(),
            "gitlab_url": inputs["gitlab_url"],
            "root_group": inputs.get("root_group"),
            "projects_count": len(projects_data),
            "projects": projects_data
        }
    
    def _generate_coverage(self, projects_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate coverage.json showing component availability per project.
        
        This is a new output that shows which components are present in each project.
        """
        coverage = {
            "version": "1.0",
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_projects": len(projects_data),
                "components": {}
            },
            "projects": {}
        }
        
        # Initialize component counters
        component_types = [
            "repository", "ci_cd", "issues", "merge_requests", "wiki",
            "releases", "packages", "webhooks", "schedules", "lfs",
            "environments", "protected_resources", "deploy_keys", "variables"
        ]
        
        for comp_type in component_types:
            coverage["summary"]["components"][comp_type] = {
                "enabled_count": 0,
                "projects_with_data": 0
            }
        
        # Process each project
        for project in projects_data:
            project_path = project["path_with_namespace"]
            project_coverage = {}
            
            components = project.get("components", {})
            for comp_type in component_types:
                comp_data = components.get(comp_type, {})
                enabled = comp_data.get("enabled", False)
                has_data = False
                
                # Check if component has actual data
                if comp_type == "repository":
                    has_data = comp_data.get("has_content", False)
                elif comp_type == "ci_cd":
                    has_data = comp_data.get("has_gitlab_ci", False)
                elif comp_type == "issues":
                    has_data = comp_data.get("has_issues", False)
                elif comp_type == "merge_requests":
                    has_data = comp_data.get("has_mrs", False)
                elif comp_type == "wiki":
                    has_data = comp_data.get("pages_count", 0) > 0
                elif comp_type in ["releases", "packages", "webhooks", "schedules", "environments", "deploy_keys", "variables"]:
                    has_data = comp_data.get("count", 0) > 0
                elif comp_type == "lfs":
                    has_data = comp_data.get("detected", False)
                elif comp_type == "protected_resources":
                    has_data = comp_data.get("has_protections", False)
                
                project_coverage[comp_type] = {
                    "enabled": enabled,
                    "has_data": has_data
                }
                
                # Update summary
                if enabled:
                    coverage["summary"]["components"][comp_type]["enabled_count"] += 1
                if has_data:
                    coverage["summary"]["components"][comp_type]["projects_with_data"] += 1
            
            coverage["projects"][project_path] = project_coverage
        
        return coverage
    
    def _generate_readiness(self, projects_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate readiness.json with migration readiness assessment.
        
        Enhanced to include all 14 components.
        """
        readiness = {
            "version": "2.0",
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_projects": len(projects_data),
                "ready": 0,
                "needs_review": 0,
                "complex": 0
            },
            "projects": {}
        }
        
        for project in projects_data:
            project_path = project["path_with_namespace"]
            assessment = self.assess_readiness(project)
            
            readiness["projects"][project_path] = assessment
            
            # Update summary
            complexity = assessment["complexity"]
            if complexity == "low":
                readiness["summary"]["ready"] += 1
            elif complexity == "medium":
                readiness["summary"]["needs_review"] += 1
            else:
                readiness["summary"]["complex"] += 1
        
        return readiness
    
    def _generate_summary(self, projects_data: List[Dict[str, Any]]) -> str:
        """Generate human-readable summary"""
        lines = [
            "=" * 60,
            "GitLab Discovery Summary",
            "=" * 60,
            f"Generated: {datetime.utcnow().isoformat()}",
            f"Total Projects: {len(projects_data)}",
            "",
            "Component Coverage:",
            "-" * 60,
        ]
        
        # Count components
        component_stats = {}
        component_types = [
            ("repository", "Repository"),
            ("ci_cd", "CI/CD"),
            ("issues", "Issues"),
            ("merge_requests", "Merge Requests"),
            ("wiki", "Wiki"),
            ("releases", "Releases"),
            ("packages", "Packages"),
            ("webhooks", "Webhooks"),
            ("schedules", "Schedules"),
            ("lfs", "Git LFS"),
            ("environments", "Environments"),
            ("protected_resources", "Protected Branches/Tags"),
            ("deploy_keys", "Deploy Keys"),
            ("variables", "CI/CD Variables")
        ]
        
        for comp_key, comp_name in component_types:
            count = sum(1 for p in projects_data 
                       if p.get("components", {}).get(comp_key, {}).get("enabled", False))
            lines.append(f"{comp_name:30s}: {count}/{len(projects_data)} projects")
        
        lines.extend([
            "",
            "=" * 60,
            "Top Projects by Complexity:",
            "-" * 60,
        ])
        
        # Show first 10 projects
        for i, project in enumerate(projects_data[:10], 1):
            lines.append(f"{i:2d}. {project['path_with_namespace']}")
            comps = project.get("components", {})
            comp_count = sum(1 for c in comps.values() if c.get("enabled", False))
            lines.append(f"    Components detected: {comp_count}/14")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def generate_artifacts(self, data: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate discovery artifacts.
        
        Returns:
            Dict mapping artifact names to paths
        """
        artifacts = {}
        output_dir = self.get_context("output_dir")
        
        if output_dir:
            output_path = Path(output_dir)
            
            for artifact_name in ["inventory", "coverage", "readiness", "summary"]:
                artifact_path = output_path / f"{artifact_name}.{'json' if artifact_name != 'summary' else 'txt'}"
                if artifact_path.exists():
                    artifacts[artifact_name] = str(artifact_path)
        
        return artifacts
    
    def assess_readiness(self, project: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess migration readiness for a project.
        
        Enhanced to consider all 14 components.
        
        Args:
            project: Project data with detected components
            
        Returns:
            Readiness assessment with blockers and recommendations
        """
        blockers = []
        notes = []
        complexity = "low"
        components = project.get("components", {})
        
        # Check for CI/CD
        ci_cd = components.get("ci_cd", {})
        if ci_cd.get("enabled") and ci_cd.get("has_gitlab_ci"):
            blockers.append("Has GitLab CI/CD pipeline - requires conversion to GitHub Actions")
            complexity = "medium"
        
        # Check for LFS
        lfs = components.get("lfs", {})
        if lfs.get("enabled") and lfs.get("detected"):
            notes.append("Uses Git LFS - ensure GitHub LFS is configured")
            if complexity == "low":
                complexity = "medium"
        
        # Check for high activity (issues and MRs)
        issues = components.get("issues", {})
        mrs = components.get("merge_requests", {})
        
        total_issues = issues.get("opened_count", 0)
        total_mrs = mrs.get("opened_count", 0)
        
        if total_issues > 100 or total_mrs > 50:
            complexity = "high"
            notes.append(f"High activity ({total_issues} issues, {total_mrs} MRs) - review migration strategy")
        elif total_issues > 30 or total_mrs > 15:
            if complexity == "low":
                complexity = "medium"
            notes.append(f"Moderate activity ({total_issues} issues, {total_mrs} MRs)")
        
        # Check for packages
        packages = components.get("packages", {})
        if packages.get("has_packages"):
            notes.append("Has packages/registry - requires migration to GitHub Packages")
            if complexity != "high":
                complexity = "medium"
        
        # Check for webhooks
        webhooks = components.get("webhooks", {})
        if webhooks.get("has_webhooks"):
            notes.append(f"{webhooks.get('count', 0)} webhooks need reconfiguration for GitHub")
        
        # Check for environments
        environments = components.get("environments", {})
        if environments.get("has_environments"):
            notes.append(f"{environments.get('count', 0)} environments need to be recreated in GitHub")
        
        # Check for protected resources
        protected = components.get("protected_resources", {})
        if protected.get("has_protections"):
            notes.append("Has branch/tag protections - need to configure GitHub branch protection rules")
        
        # Check for deploy keys
        deploy_keys = components.get("deploy_keys", {})
        if deploy_keys.get("has_deploy_keys"):
            notes.append(f"{deploy_keys.get('count', 0)} deploy keys need to be recreated in GitHub")
        
        # Check for variables
        variables = components.get("variables", {})
        if variables.get("has_variables"):
            notes.append(f"{variables.get('count', 0)} CI/CD variables need to be migrated to GitHub Secrets/Variables")
        
        # Check if archived
        if project.get("archived"):
            notes.append("Project is archived - consider excluding from migration")
            complexity = "low"
        
        # Count total components with data
        components_with_data = sum(
            1 for comp in components.values()
            if isinstance(comp, dict) and comp.get("enabled") and (
                comp.get("has_data") or 
                comp.get("count", 0) > 0 or
                comp.get("detected", False)
            )
        )
        
        return {
            "complexity": complexity,
            "blockers": blockers,
            "notes": notes,
            "components_detected": len(components),
            "components_with_data": components_with_data,
            "recommendation": self._get_recommendation(complexity, blockers, notes)
        }
    
    def _get_recommendation(self, complexity: str, blockers: List[str], notes: List[str]) -> str:
        """Get migration recommendation based on assessment"""
        if complexity == "low":
            return "Ready for migration - straightforward project with minimal complexity"
        elif complexity == "medium":
            return "Needs review - some components require manual configuration or conversion"
        else:
            return "Complex migration - requires careful planning and staged approach"
