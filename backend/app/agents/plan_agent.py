"""Plan Agent - Generate migration execution plan using Microsoft Agent Framework"""

from typing import Any, Dict, List, Optional, Set, Tuple
from pathlib import Path
from datetime import datetime
import json
import hashlib
from collections import defaultdict, deque
from app.agents.base_agent import BaseAgent, AgentResult
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ActionType:
    """Action type constants"""
    # Repository
    REPO_CREATE = "repo_create"
    REPO_PUSH = "repo_push"
    REPO_CONFIGURE = "repo_configure"
    LFS_CONFIGURE = "lfs_configure"
    
    # CI/CD
    WORKFLOW_COMMIT = "workflow_commit"
    ENVIRONMENT_CREATE = "environment_create"
    SECRET_SET = "secret_set"
    VARIABLE_SET = "variable_set"
    SCHEDULE_CREATE = "schedule_create"
    
    # Issues
    LABEL_CREATE = "label_create"
    MILESTONE_CREATE = "milestone_create"
    ISSUE_CREATE = "issue_create"
    
    # Pull Requests
    PR_CREATE = "pr_create"
    PR_COMMENT_ADD = "pr_comment_add"
    
    # Wiki
    WIKI_PUSH = "wiki_push"
    WIKI_COMMIT = "wiki_commit"
    
    # Releases
    RELEASE_CREATE = "release_create"
    RELEASE_ASSET_UPLOAD = "release_asset_upload"
    
    # Packages
    PACKAGE_PUBLISH = "package_publish"
    
    # Settings
    PROTECTION_SET = "protection_set"
    COLLABORATOR_ADD = "collaborator_add"
    TEAM_CREATE = "team_create"
    CODEOWNERS_COMMIT = "codeowners_commit"
    
    # Webhooks
    WEBHOOK_CREATE = "webhook_create"
    WEBHOOK_CONFIGURE = "webhook_configure"
    
    # Preservation
    ARTIFACT_COMMIT = "artifact_commit"
    ATTACHMENTS_COMMIT = "attachments_commit"


class Phase:
    """Phase constants"""
    FOUNDATION = "foundation"
    CI_SETUP = "ci_setup"
    ISSUE_SETUP = "issue_setup"
    ISSUE_IMPORT = "issue_import"
    PR_IMPORT = "pr_import"
    WIKI_IMPORT = "wiki_import"
    RELEASE_IMPORT = "release_import"
    PACKAGE_IMPORT = "package_import"
    GOVERNANCE = "governance"
    INTEGRATIONS = "integrations"
    PRESERVATION = "preservation"


class PlanGenerator:
    """Core plan generation logic"""
    
    def __init__(self, run_id: str, project_id: str, gitlab_project: str, github_target: str):
        self.run_id = run_id
        self.project_id = project_id
        self.gitlab_project = gitlab_project
        self.github_target = github_target
        self.actions = []
        self.action_counter = 0
        self.dependency_graph = {}
        self.action_map = {}
    
    def generate_action_id(self) -> str:
        """Generate unique action ID"""
        self.action_counter += 1
        return f"action-{self.action_counter:03d}"
    
    def generate_idempotency_key(self, action_type: str, entity_id: str, extra: str = "") -> str:
        """
        Generate deterministic idempotency key.
        Format: {action_type}-{entity_id_clean}-{hash}
        
        Note: entity_id should be a stable identifier from the source data (e.g., issue IID, label name)
        to ensure the same action in different runs gets the same key.
        """
        # Clean entity_id for use in key (remove special chars, limit length)
        entity_id_clean = str(entity_id).replace("/", "-").replace(":", "-")[:50]
        
        # Hash includes all identifying information for determinism
        data = f"{self.project_id}:{action_type}:{entity_id}:{extra}"
        hash_suffix = hashlib.sha256(data.encode()).hexdigest()[:8]
        return f"{action_type}-{entity_id_clean}-{hash_suffix}"
    
    def add_action(
        self,
        action_type: str,
        component: str,
        phase: str,
        description: str,
        parameters: Dict[str, Any],
        dependencies: List[str] = None,
        dry_run_safe: bool = True,
        reversible: bool = True,
        estimated_duration_seconds: int = 5,
        requires_user_input: bool = False,
        skip_if: Optional[Dict[str, str]] = None
    ) -> str:
        """Add an action to the plan"""
        action_id = self.generate_action_id()
        
        # Generate idempotency key - use stable identifiers from source data
        # Priority: explicit IDs (iid, tag_name) > names > action_id
        entity_id = (
            parameters.get("gitlab_issue_iid") or 
            parameters.get("gitlab_mr_iid") or
            parameters.get("tag_name") or
            parameters.get("name") or 
            parameters.get("title") or 
            parameters.get("branch") or
            action_id
        )
        idempotency_key = self.generate_idempotency_key(action_type, str(entity_id))
        
        action = {
            "id": action_id,
            "type": action_type,
            "component": component,
            "phase": phase,
            "description": description,
            "dependencies": dependencies or [],
            "idempotency_key": idempotency_key,
            "parameters": parameters,
            "dry_run_safe": dry_run_safe,
            "reversible": reversible,
            "estimated_duration_seconds": estimated_duration_seconds
        }
        
        if requires_user_input:
            action["requires_user_input"] = True
        
        if skip_if:
            action["skip_if"] = skip_if
        
        self.actions.append(action)
        self.action_map[action_id] = action
        self.dependency_graph[action_id] = dependencies or []
        
        return action_id
    
    def validate_dependencies(self) -> Tuple[bool, List[str]]:
        """Validate dependency graph - check all dependencies exist and no cycles"""
        errors = []
        
        # Check all dependencies exist
        for action_id, deps in self.dependency_graph.items():
            for dep_id in deps:
                if dep_id not in self.action_map:
                    errors.append(f"Action {action_id} depends on non-existent action {dep_id}")
        
        # Check for circular dependencies using DFS
        visited = set()
        rec_stack = set()
        
        def has_cycle(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            
            for dep in self.dependency_graph.get(node, []):
                if dep not in visited:
                    if has_cycle(dep):
                        return True
                elif dep in rec_stack:
                    errors.append(f"Circular dependency detected involving {node} and {dep}")
                    return True
            
            rec_stack.remove(node)
            return False
        
        for action_id in self.dependency_graph:
            if action_id not in visited:
                has_cycle(action_id)
        
        return len(errors) == 0, errors
    
    def topological_sort(self) -> List[str]:
        """Perform topological sort to get execution order using Kahn's algorithm"""
        in_degree = {action_id: 0 for action_id in self.action_map}
        
        # Calculate in-degrees (count dependencies for each action)
        for action_id, deps in self.dependency_graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[action_id] += 1
        
        # Build reverse dependency map for efficient lookup
        reverse_deps = defaultdict(list)
        for action_id, deps in self.dependency_graph.items():
            for dep in deps:
                reverse_deps[dep].append(action_id)
        
        # Find all nodes with in-degree 0
        queue = deque([action_id for action_id, degree in in_degree.items() if degree == 0])
        sorted_actions = []
        
        while queue:
            action_id = queue.popleft()
            sorted_actions.append(action_id)
            
            # Reduce in-degree for dependent actions using reverse map
            for dependent_id in reverse_deps[action_id]:
                if dependent_id not in sorted_actions:
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        queue.append(dependent_id)
        
        return sorted_actions
    
    def organize_into_phases(self) -> List[Dict[str, Any]]:
        """Organize actions into phases"""
        phase_actions = defaultdict(list)
        
        for action in self.actions:
            phase_actions[action["phase"]].append(action["id"])
        
        # Define phase order
        phase_order = [
            (Phase.FOUNDATION, "Create repository and push code", False),
            (Phase.CI_SETUP, "Set up CI/CD workflows and environments", False),
            (Phase.ISSUE_SETUP, "Create labels and milestones", False),
            (Phase.ISSUE_IMPORT, "Import issues", True),
            (Phase.PR_IMPORT, "Import pull requests", True),
            (Phase.WIKI_IMPORT, "Import wiki", False),
            (Phase.RELEASE_IMPORT, "Import releases", False),
            (Phase.PACKAGE_IMPORT, "Publish packages", False),
            (Phase.GOVERNANCE, "Set protections and permissions", False),
            (Phase.INTEGRATIONS, "Configure webhooks", False),
            (Phase.PRESERVATION, "Commit preservation artifacts", False),
        ]
        
        phases = []
        for order, (phase_name, description, parallel_safe) in enumerate(phase_order, 1):
            if phase_name in phase_actions and phase_actions[phase_name]:
                phase_data = {
                    "name": phase_name,
                    "description": description,
                    "actions": phase_actions[phase_name],
                    "order": order
                }
                if parallel_safe:
                    phase_data["parallel_safe"] = True
                phases.append(phase_data)
        
        return phases
    
    def build_plan(self, export_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Build complete plan"""
        # Validate dependencies
        valid, errors = self.validate_dependencies()
        if not valid:
            raise ValueError(f"Dependency validation failed: {errors}")
        
        # Organize phases
        phases = self.organize_into_phases()
        
        # Calculate statistics
        actions_by_type = defaultdict(int)
        total_duration = 0
        requires_user_input_count = 0
        
        for action in self.actions:
            actions_by_type[action["type"]] += 1
            total_duration += action["estimated_duration_seconds"]
            if action.get("requires_user_input"):
                requires_user_input_count += 1
        
        plan = {
            "version": "1.0",
            "run_id": self.run_id,
            "project_id": self.project_id,
            "gitlab_project": self.gitlab_project,
            "github_target": self.github_target,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "mode": "PLAN_ONLY",
            
            "summary": {
                "total_actions": len(self.actions),
                "actions_by_type": dict(actions_by_type),
                "estimated_duration_minutes": int(total_duration / 60),
                "requires_user_input": requires_user_input_count > 0,
                "blocking_issues": []
            },
            
            "actions": self.actions,
            "phases": phases,
            
            "validation": {
                "all_dependencies_resolvable": valid,
                "no_circular_dependencies": valid,
                "all_required_inputs_identified": True,
                "estimated_github_api_calls": len(self.actions),
                "estimated_rate_limit_buffer": "sufficient"
            },
            
            "metadata": {
                "generated_by": "PlanAgent",
                "generator_version": "1.0",
                "gitlab_version": export_data.get("gitlab_version", "16.5.0") if export_data else "16.5.0",
                "github_api_version": "2022-11-28"
            }
        }
        
        return plan


class PlanAgent(BaseAgent):
    """
    Plan Agent for generating executable migration plans.
    
    Using Microsoft Agent Framework patterns:
    - Workflow orchestration
    - Dependency management
    - Intelligent planning with LLM (future)
    - Idempotency key generation
    """
    
    def __init__(self):
        super().__init__(
            agent_name="PlanAgent",
            instructions="""
            You are specialized in creating executable migration plans.
            Your responsibilities:
            1. Generate ordered list of migration actions
            2. Compute dependencies between actions
            3. Create idempotency keys for safe retries
            4. Organize actions into phases
            5. Identify required user inputs (secrets, mappings)
            6. Validate plan completeness and safety
            7. Generate human-readable plan documentation
            
            Ensure plans are deterministic, safe, and resumable.
            """
        )
    
    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        """Validate plan inputs"""
        # Only output_dir is strictly required, other fields have defaults
        required = ["output_dir"]
        has_required = all(field in inputs for field in required)
        
        # Optionally warn if important fields are missing but provide defaults
        recommended = ["run_id", "project_id", "gitlab_project", "github_target"]
        missing_recommended = [f for f in recommended if f not in inputs]
        if missing_recommended and has_required:
            self.log_event("WARN", f"Using defaults for: {', '.join(missing_recommended)}")
        
        return has_required
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute plan generation"""
        self.log_event("INFO", "Starting plan generation")
        
        try:
            output_dir = Path(inputs["output_dir"])
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Extract configuration
            run_id = inputs.get("run_id", "test-run-001")
            project_id = inputs.get("project_id", "test-project-001")
            gitlab_project = inputs.get("gitlab_project", "namespace/project")
            github_target = inputs.get("github_target", "org/repo")
            
            # Get transform and export data
            transform_data = inputs.get("transform_data", {})
            export_data = inputs.get("export_data", {})
            
            self.log_event("INFO", f"Generating plan for {gitlab_project} -> {github_target}")
            
            # Create plan generator
            generator = PlanGenerator(run_id, project_id, gitlab_project, github_target)
            
            # Generate plan actions
            user_inputs_required = []
            self._generate_plan_actions(generator, export_data, transform_data, user_inputs_required)
            
            # Build complete plan
            plan = generator.build_plan(export_data)
            plan["user_inputs_required"] = user_inputs_required
            
            # Generate artifacts
            artifacts = self._generate_plan_artifacts(output_dir, plan, generator)
            
            self.log_event("INFO", f"Plan generated successfully: {len(plan['actions'])} actions")
            
            return AgentResult(
                status="success",
                outputs={
                    "plan": plan,
                    "plan_complete": True,
                    "total_actions": len(plan["actions"]),
                    "requires_user_input": len(user_inputs_required) > 0
                },
                artifacts=artifacts,
                errors=[]
            ).to_dict()
            
        except Exception as e:
            self.log_event("ERROR", f"Plan generation failed: {str(e)}")
            return AgentResult(
                status="failed",
                outputs={},
                artifacts=[],
                errors=[{"step": "plan", "message": str(e)}]
            ).to_dict()
    
    def _generate_plan_actions(
        self,
        generator: PlanGenerator,
        export_data: Dict[str, Any],
        transform_data: Dict[str, Any],
        user_inputs_required: List[Dict[str, Any]]
    ):
        """Generate all plan actions"""
        
        # Phase 1: Foundation - Repository creation and code push
        repo_create_id = generator.add_action(
            action_type=ActionType.REPO_CREATE,
            component="repository",
            phase=Phase.FOUNDATION,
            description=f"Create GitHub repository {generator.github_target}",
            parameters={
                "org": generator.github_target.split("/")[0],
                "name": generator.github_target.split("/")[1],
                "description": export_data.get("description", "Migrated from GitLab"),
                "private": export_data.get("visibility", "private") == "private",
                "has_issues": True,
                "has_projects": True,
                "has_wiki": export_data.get("has_wiki", False)
            },
            dry_run_safe=True,
            reversible=True,
            estimated_duration_seconds=5
        )
        
        repo_push_id = generator.add_action(
            action_type=ActionType.REPO_PUSH,
            component="repository",
            phase=Phase.FOUNDATION,
            description="Push git bundle to GitHub",
            parameters={
                "bundle_path": f"export/{generator.gitlab_project}/repo.bundle",
                "target_repo": generator.github_target,
                "force": False
            },
            dependencies=[repo_create_id],
            dry_run_safe=False,
            reversible=False,
            estimated_duration_seconds=120
        )
        
        # LFS configuration if needed
        if export_data.get("has_lfs", False):
            generator.add_action(
                action_type=ActionType.LFS_CONFIGURE,
                component="repository",
                phase=Phase.FOUNDATION,
                description="Configure Git LFS and push objects",
                parameters={
                    "lfs_objects_path": f"export/{generator.gitlab_project}/lfs/",
                    "target_repo": generator.github_target
                },
                dependencies=[repo_push_id],
                dry_run_safe=False,
                reversible=False,
                estimated_duration_seconds=180,
                skip_if={"condition": "no_lfs", "check": "lfs_objects_count == 0"}
            )
        
        # Phase 2: CI/CD - Workflows, environments, secrets
        workflows = transform_data.get("workflows", [])
        for workflow in workflows:
            generator.add_action(
                action_type=ActionType.WORKFLOW_COMMIT,
                component="ci",
                phase=Phase.CI_SETUP,
                description=f"Commit workflow: {workflow.get('name', 'workflow.yml')}",
                parameters={
                    "workflow_path": workflow.get("source_path"),
                    "target_path": f".github/workflows/{workflow.get('name', 'workflow.yml')}",
                    "target_repo": generator.github_target,
                    "branch": "main",
                    "commit_message": f"Add {workflow.get('name')} workflow (migrated from GitLab CI)"
                },
                dependencies=[repo_push_id],
                dry_run_safe=False,
                reversible=True,
                estimated_duration_seconds=10
            )
        
        # Environments
        environments = transform_data.get("environments", [])
        env_action_ids = {}
        for env in environments:
            env_id = generator.add_action(
                action_type=ActionType.ENVIRONMENT_CREATE,
                component="ci",
                phase=Phase.CI_SETUP,
                description=f"Create environment: {env.get('name')}",
                parameters={
                    "target_repo": generator.github_target,
                    "environment_name": env.get("name"),
                    "wait_timer": 0,
                    "reviewers": [],
                    "deployment_branch_policy": "protected"
                },
                dependencies=[repo_create_id],
                dry_run_safe=True,
                reversible=True,
                estimated_duration_seconds=5
            )
            env_action_ids[env.get("name")] = env_id
            
            # Secrets for this environment
            for secret in env.get("secrets", []):
                requires_input = secret.get("masked", False) or secret.get("value") is None
                if requires_input:
                    user_inputs_required.append({
                        "type": "secret_value",
                        "key": secret.get("key"),
                        "scope": "environment",
                        "environment": env.get("name"),
                        "reason": "GitLab variable was masked, value not retrievable",
                        "required": True
                    })
                
                generator.add_action(
                    action_type=ActionType.SECRET_SET,
                    component="ci",
                    phase=Phase.CI_SETUP,
                    description=f"Set secret: {secret.get('key')} ({env.get('name')})",
                    parameters={
                        "target_repo": generator.github_target,
                        "secret_name": secret.get("key"),
                        "scope": "environment",
                        "environment": env.get("name"),
                        "value": "${USER_INPUT_REQUIRED}" if requires_input else secret.get("value"),
                        "value_source": "user_input" if requires_input else "export"
                    },
                    dependencies=[env_id],
                    dry_run_safe=True,
                    reversible=True,
                    estimated_duration_seconds=3,
                    requires_user_input=requires_input
                )
        
        # Phase 3: Issue Setup - Labels and milestones
        labels = export_data.get("labels", [])
        label_action_ids = {}
        for label in labels:
            label_id = generator.add_action(
                action_type=ActionType.LABEL_CREATE,
                component="issues",
                phase=Phase.ISSUE_SETUP,
                description=f"Create label: {label.get('name')}",
                parameters={
                    "target_repo": generator.github_target,
                    "name": label.get("name"),
                    "color": label.get("color", "000000").replace("#", ""),
                    "description": label.get("description", "")
                },
                dependencies=[repo_create_id],
                dry_run_safe=True,
                reversible=True,
                estimated_duration_seconds=2
            )
            label_action_ids[label.get("name")] = label_id
        
        milestones = export_data.get("milestones", [])
        milestone_action_ids = {}
        for milestone in milestones:
            milestone_id = generator.add_action(
                action_type=ActionType.MILESTONE_CREATE,
                component="issues",
                phase=Phase.ISSUE_SETUP,
                description=f"Create milestone: {milestone.get('title')}",
                parameters={
                    "target_repo": generator.github_target,
                    "title": milestone.get("title"),
                    "description": milestone.get("description", ""),
                    "due_on": milestone.get("due_date"),
                    "state": milestone.get("state", "open")
                },
                dependencies=[repo_create_id],
                dry_run_safe=True,
                reversible=True,
                estimated_duration_seconds=2
            )
            milestone_action_ids[milestone.get("title")] = milestone_id
        
        # Phase 4: Issue Import
        issues = export_data.get("issues", [])
        for issue in issues:
            deps = [repo_create_id]
            
            # Add label dependencies
            issue_labels = issue.get("labels", [])
            for label_name in issue_labels:
                if label_name in label_action_ids:
                    deps.append(label_action_ids[label_name])
            
            # Add milestone dependency
            issue_milestone = issue.get("milestone")
            if issue_milestone and issue_milestone in milestone_action_ids:
                deps.append(milestone_action_ids[issue_milestone])
            
            # Keep full title (GitHub supports up to 256 chars)
            generator.add_action(
                action_type=ActionType.ISSUE_CREATE,
                component="issues",
                phase=Phase.ISSUE_IMPORT,
                description=f"Import issue #{issue.get('iid')}: {issue.get('title', 'Untitled')[:80]}{'...' if len(issue.get('title', '')) > 80 else ''}",
                parameters={
                    "target_repo": generator.github_target,
                    "gitlab_issue_iid": issue.get("iid"),
                    "title": issue.get("title"),
                    "body": issue.get("description", ""),
                    "labels": issue_labels,
                    "milestone": issue_milestone,
                    "assignees": issue.get("assignees", []),
                    "state": issue.get("state", "open"),
                    "comments": issue.get("comments", [])
                },
                dependencies=deps,
                dry_run_safe=False,
                reversible=False,
                estimated_duration_seconds=5
            )
        
        # Phase 5: PR Import
        merge_requests = export_data.get("merge_requests", [])
        default_branch = export_data.get("default_branch", "main")
        
        for mr in merge_requests:
            deps = [repo_push_id]
            
            # Add label dependencies
            mr_labels = mr.get("labels", [])
            for label_name in mr_labels:
                if label_name in label_action_ids:
                    deps.append(label_action_ids[label_name])
            
            # Keep full title (GitHub supports up to 256 chars)
            generator.add_action(
                action_type=ActionType.PR_CREATE,
                component="pull_requests",
                phase=Phase.PR_IMPORT,
                description=f"Import MR !{mr.get('iid')} as PR: {mr.get('title', 'Untitled')[:80]}{'...' if len(mr.get('title', '')) > 80 else ''}",
                parameters={
                    "target_repo": generator.github_target,
                    "gitlab_mr_iid": mr.get("iid"),
                    "title": mr.get("title"),
                    "body": mr.get("description", ""),
                    "head": mr.get("source_branch"),
                    "base": mr.get("target_branch", default_branch),
                    "labels": mr_labels,
                    "reviewers": mr.get("reviewers", []),
                    "state": mr.get("state", "open"),
                    "comments": mr.get("comments", []),
                    "ensure_branch_exists": True
                },
                dependencies=deps,
                dry_run_safe=False,
                reversible=False,
                estimated_duration_seconds=10
            )
        
        # Phase 6: Wiki Import
        if export_data.get("has_wiki", False):
            generator.add_action(
                action_type=ActionType.WIKI_PUSH,
                component="wiki",
                phase=Phase.WIKI_IMPORT,
                description="Push wiki pages to GitHub wiki",
                parameters={
                    "wiki_bundle_path": f"export/{generator.gitlab_project}/wiki.bundle",
                    "target_repo": generator.github_target
                },
                dependencies=[repo_create_id],
                dry_run_safe=False,
                reversible=False,
                estimated_duration_seconds=30,
                skip_if={"condition": "no_wiki", "check": "wiki_pages_count == 0"}
            )
        
        # Phase 7: Release Import
        releases = export_data.get("releases", [])
        for release in releases:
            tag_name = release.get("tag_name")
            
            # Create release
            release_action_id = generator.add_action(
                action_type=ActionType.RELEASE_CREATE,
                component="releases",
                phase=Phase.RELEASE_IMPORT,
                description=f"Create release: {tag_name}",
                parameters={
                    "target_repo": generator.github_target,
                    "tag": tag_name,
                    "name": release.get("name"),
                    "body": release.get("description", ""),
                    "draft": False,
                    "prerelease": False,
                    "gitlab_release_id": release.get("id")
                },
                dependencies=[repo_push_id],
                dry_run_safe=False,
                reversible=True,
                estimated_duration_seconds=20
            )
            
            # Upload release assets
            assets = release.get("assets", {})
            links = assets.get("links", []) if isinstance(assets, dict) else []
            
            for asset in links:
                local_path = asset.get("local_path")
                asset_name = asset.get("name")
                
                # Only create upload action if asset was downloaded
                if local_path and asset_name:
                    generator.add_action(
                        action_type=ActionType.RELEASE_ASSET_UPLOAD,
                        component="releases",
                        phase=Phase.RELEASE_IMPORT,
                        description=f"Upload asset: {tag_name}/{asset_name}",
                        parameters={
                            "target_repo": generator.github_target,
                            "release_tag": tag_name,
                            "asset_path": local_path,
                            "asset_name": asset_name,
                            "content_type": asset.get("content_type", "application/octet-stream")
                        },
                        dependencies=[release_action_id],
                        dry_run_safe=False,
                        reversible=True,
                        estimated_duration_seconds=10
                    )
        
        # Phase 8: Package Import
        # Read packages from export directory
        output_dir = Path(export_data.get("output_dir", ""))
        packages_file = output_dir / "packages" / "packages.json"
        packages = []
        
        if packages_file.exists():
            try:
                with open(packages_file, 'r') as f:
                    packages = json.load(f)
                self.log_event("INFO", f"Loaded {len(packages)} packages from export")
            except Exception as e:
                self.log_event("WARNING", f"Failed to load packages.json: {e}")
        
        for package in packages:
            package_id = package.get("id")
            package_name = package.get("name", "unknown")
            package_type = package.get("package_type", "unknown")
            package_version = package.get("version", "unknown")
            migrable = package.get("migrable", False)
            files = package.get("files", [])
            
            # Generate action description based on migrability
            if not migrable:
                description = f"Document non-migrable package: {package_type}/{package_name}@{package_version}"
            elif not files:
                description = f"Document package without files: {package_type}/{package_name}@{package_version}"
            else:
                description = f"Publish {package_type} package: {package_name}@{package_version}"
            
            generator.add_action(
                action_type=ActionType.PACKAGE_PUBLISH,
                component="packages",
                phase=Phase.PACKAGE_IMPORT,
                description=description,
                parameters={
                    "target_repo": generator.github_target,
                    "package_type": package_type,
                    "package_name": package_name,
                    "version": package_version,
                    "files": files,
                    "migrable": migrable,
                    "package_id": package_id
                },
                dependencies=[repo_create_id],
                dry_run_safe=False,
                reversible=False,
                estimated_duration_seconds=300 if files else 5,
                skip_if=None  # Don't skip, we want to report status
            )
        
        # Add a summary log if there are non-migrable packages
        non_migrable_packages = [p for p in packages if not p.get("migrable", False)]
        if non_migrable_packages:
            self.log_event("INFO", f"Found {len(non_migrable_packages)} non-migrable packages that require manual migration")
        
        
        # Phase 9: Governance - Branch protection
        branch_protections = transform_data.get("branch_protections", [])
        for protection in branch_protections:
            generator.add_action(
                action_type=ActionType.PROTECTION_SET,
                component="settings",
                phase=Phase.GOVERNANCE,
                description=f"Set branch protection: {protection.get('branch')}",
                parameters={
                    "target_repo": generator.github_target,
                    "branch": protection.get("branch"),
                    "required_status_checks": protection.get("required_status_checks"),
                    "enforce_admins": protection.get("enforce_admins", True),
                    "required_pull_request_reviews": protection.get("required_pull_request_reviews"),
                    "restrictions": None,
                    "allow_force_pushes": False,
                    "allow_deletions": False
                },
                dependencies=[repo_push_id],
                dry_run_safe=True,
                reversible=True,
                estimated_duration_seconds=5
            )
        
        # Phase 10: Integrations - Webhooks
        webhooks = export_data.get("webhooks", [])
        for webhook in webhooks:
            requires_input = webhook.get("secret") is None
            if requires_input:
                user_inputs_required.append({
                    "type": "webhook_secret",
                    "url": webhook.get("url"),
                    "reason": "Webhook secret not available in export",
                    "required": False,
                    "fallback": "generate_random"
                })
            
            generator.add_action(
                action_type=ActionType.WEBHOOK_CREATE,
                component="webhooks",
                phase=Phase.INTEGRATIONS,
                description=f"Create webhook: {webhook.get('url', 'webhook')[:60]}{'...' if len(webhook.get('url', '')) > 60 else ''}",
                parameters={
                    "target_repo": generator.github_target,
                    "url": webhook.get("url"),
                    "content_type": "json",
                    "secret": "${USER_INPUT_REQUIRED}" if requires_input else webhook.get("secret"),
                    "events": webhook.get("events", ["push", "pull_request"]),
                    "active": True
                },
                dependencies=[repo_create_id],
                dry_run_safe=True,
                reversible=True,
                estimated_duration_seconds=3,
                requires_user_input=requires_input
            )
        
        # Phase 11: Preservation - Commit artifacts
        if export_data.get("preserve_pipelines", False):
            generator.add_action(
                action_type=ActionType.ARTIFACT_COMMIT,
                component="preservation",
                phase=Phase.PRESERVATION,
                description="Commit migration artifacts",
                parameters={
                    "target_repo": generator.github_target,
                    "source_path": f"export/{generator.gitlab_project}/pipelines/",
                    "target_path": "migration/gitlab-pipelines/",
                    "branch": "main",
                    "commit_message": "Add GitLab pipeline history (preserved)"
                },
                dependencies=[repo_push_id],
                dry_run_safe=False,
                reversible=False,
                estimated_duration_seconds=15
            )
    
    def _generate_plan_artifacts(
        self,
        output_dir: Path,
        plan: Dict[str, Any],
        generator: PlanGenerator
    ) -> List[str]:
        """Generate plan artifacts"""
        artifacts = []
        
        # 1. plan.json
        plan_json_path = output_dir / "plan.json"
        with open(plan_json_path, "w") as f:
            json.dump(plan, f, indent=2)
        artifacts.append(str(plan_json_path))
        self.log_event("INFO", f"Generated plan.json: {plan_json_path}")
        
        # 2. dependency_graph.json
        dep_graph_path = output_dir / "dependency_graph.json"
        with open(dep_graph_path, "w") as f:
            json.dump(generator.dependency_graph, f, indent=2)
        artifacts.append(str(dep_graph_path))
        
        # 3. user_inputs_required.json
        user_inputs_path = output_dir / "user_inputs_required.json"
        with open(user_inputs_path, "w") as f:
            json.dump(plan.get("user_inputs_required", []), f, indent=2)
        artifacts.append(str(user_inputs_path))
        
        # 4. plan_stats.json
        stats = {
            "total_actions": plan["summary"]["total_actions"],
            "actions_by_type": plan["summary"]["actions_by_type"],
            "actions_by_phase": {phase["name"]: len(phase["actions"]) for phase in plan["phases"]},
            "estimated_duration_minutes": plan["summary"]["estimated_duration_minutes"],
            "requires_user_input": plan["summary"]["requires_user_input"],
            "user_inputs_count": len(plan.get("user_inputs_required", []))
        }
        stats_path = output_dir / "plan_stats.json"
        with open(stats_path, "w") as f:
            json.dump(stats, f, indent=2)
        artifacts.append(str(stats_path))
        
        # 5. plan.md (human-readable)
        plan_md = self._generate_plan_markdown(plan)
        plan_md_path = output_dir / "plan.md"
        with open(plan_md_path, "w") as f:
            f.write(plan_md)
        artifacts.append(str(plan_md_path))
        
        return artifacts
    
    def _generate_plan_markdown(self, plan: Dict[str, Any]) -> str:
        """Generate human-readable markdown plan"""
        lines = [
            "# Migration Plan Summary",
            "",
            f"**Source**: {plan['gitlab_project']}",
            f"**Target**: {plan['github_target']}",
            f"**Generated**: {plan['created_at']}",
            "",
            "## Overview",
            "",
            f"- **Total Actions**: {plan['summary']['total_actions']}",
            f"- **Estimated Duration**: {plan['summary']['estimated_duration_minutes']} minutes",
            f"- **Requires User Input**: {'Yes' if plan['summary']['requires_user_input'] else 'No'}",
            "",
            "## Actions by Type",
            ""
        ]
        
        for action_type, count in sorted(plan['summary']['actions_by_type'].items()):
            lines.append(f"- `{action_type}`: {count}")
        
        lines.extend(["", "## Execution Phases", ""])
        
        for phase in plan['phases']:
            lines.append(f"### Phase {phase['order']}: {phase['name']}")
            lines.append(f"*{phase['description']}*")
            lines.append(f"")
            lines.append(f"**Actions**: {len(phase['actions'])}")
            if phase.get("parallel_safe"):
                lines.append("**Parallel Execution**: Supported")
            lines.append("")
        
        if plan.get("user_inputs_required"):
            lines.extend(["## Required User Inputs", ""])
            for user_input in plan["user_inputs_required"]:
                lines.append(f"- **{user_input.get('type')}**: {user_input.get('key', user_input.get('url'))}")
                lines.append(f"  - Reason: {user_input.get('reason')}")
                lines.append(f"  - Required: {'Yes' if user_input.get('required') else 'No'}")
                lines.append("")
        
        lines.extend([
            "## Validation",
            "",
            f"- Dependencies Resolvable: {'✓' if plan['validation']['all_dependencies_resolvable'] else '✗'}",
            f"- No Circular Dependencies: {'✓' if plan['validation']['no_circular_dependencies'] else '✗'}",
            f"- Required Inputs Identified: {'✓' if plan['validation']['all_required_inputs_identified'] else '✗'}",
            ""
        ])
        
        return "\n".join(lines)
    
    def generate_artifacts(self, data: Dict[str, Any]) -> Dict[str, str]:
        """Generate plan artifacts"""
        return {
            "plan_json": "plan/plan.json",
            "plan_markdown": "plan/plan.md",
            "dependency_graph": "plan/dependency_graph.json",
            "user_inputs_required": "plan/user_inputs_required.json",
            "plan_stats": "plan/plan_stats.json"
        }
