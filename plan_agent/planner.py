"""
Plan Generator - Core logic for generating migration plans from transform outputs.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .dependency_graph import DependencyGraph
from .schema import Action, ActionType, PhaseType, Plan, generate_idempotency_key


class PlanGenerator:
    """
    Generates migration plans from transform outputs.
    """
    
    def __init__(self, project_id: str, run_id: str):
        """
        Initialize the plan generator.
        
        Args:
            project_id: Source project identifier
            run_id: Unique run identifier
        """
        self.project_id = project_id
        self.run_id = run_id
        self.actions: list[Action] = []
        self.action_counter = 0
        self.dependency_graph = DependencyGraph()
    
    def _generate_action_id(self, action_type: ActionType, entity_id: str = "") -> str:
        """Generate a unique action ID."""
        self.action_counter += 1
        suffix = f"_{entity_id}" if entity_id else ""
        return f"action_{self.action_counter:04d}_{action_type.value}{suffix}"
    
    def add_action(
        self,
        action_type: ActionType,
        phase: PhaseType,
        description: str,
        parameters: dict[str, Any],
        entity_id: str = "",
        dependencies: list[str] | None = None,
        requires_user_input: bool = False,
        user_input_fields: list[dict[str, Any]] | None = None,
    ) -> str:
        """
        Add an action to the plan.
        
        Args:
            action_type: Type of action
            phase: Phase this action belongs to
            description: Human-readable description
            parameters: Action-specific parameters
            entity_id: Entity identifier for idempotency key
            dependencies: List of action IDs this depends on
            requires_user_input: Whether user input is required
            user_input_fields: Fields requiring user input
            
        Returns:
            Action ID
        """
        action_id = self._generate_action_id(action_type, entity_id)
        
        # Generate idempotency key
        additional_data = json.dumps(parameters, sort_keys=True)
        idempotency_key = generate_idempotency_key(
            self.project_id,
            action_type,
            entity_id or action_id,
            additional_data
        )
        
        action: Action = {
            "id": action_id,
            "action_type": action_type.value,
            "idempotency_key": idempotency_key,
            "description": description,
            "phase": phase.value,
            "dependencies": dependencies or [],
            "parameters": parameters,
            "requires_user_input": requires_user_input,
        }
        
        if user_input_fields:
            action["user_input_fields"] = user_input_fields
        
        self.actions.append(action)
        
        # Add to dependency graph
        self.dependency_graph.add_node(action_id, action)
        for dep_id in (dependencies or []):
            self.dependency_graph.add_dependency(action_id, dep_id)
        
        return action_id
    
    def generate_from_transform(self, transform_output: dict[str, Any]) -> Plan:
        """
        Generate a migration plan from transform outputs.
        
        Args:
            transform_output: Transform agent output containing converted data
            
        Returns:
            Complete migration plan
        """
        # Phase 1: Repository Creation
        repo_action = self.add_action(
            ActionType.CREATE_REPOSITORY,
            PhaseType.REPOSITORY_CREATION,
            f"Create GitHub repository for {self.project_id}",
            {
                "name": transform_output.get("repository", {}).get("name", self.project_id),
                "description": transform_output.get("repository", {}).get("description", ""),
                "visibility": transform_output.get("repository", {}).get("visibility", "private"),
            },
            entity_id="repository"
        )
        
        # Phase 2: Code Push
        code_action = self.add_action(
            ActionType.PUSH_CODE,
            PhaseType.CODE_PUSH,
            "Push repository code to GitHub",
            {
                "branches": transform_output.get("repository", {}).get("branches", []),
                "default_branch": transform_output.get("repository", {}).get("default_branch", "main"),
            },
            entity_id="code",
            dependencies=[repo_action]
        )
        
        # Check for LFS
        if transform_output.get("repository", {}).get("has_lfs", False):
            lfs_action = self.add_action(
                ActionType.PUSH_LFS,
                PhaseType.CODE_PUSH,
                "Push Git LFS objects",
                {"lfs_objects": transform_output.get("repository", {}).get("lfs_objects", [])},
                entity_id="lfs",
                dependencies=[code_action]
            )
        
        # Phase 3: Labels and Milestones
        label_actions = []
        for label in transform_output.get("labels", []):
            label_action = self.add_action(
                ActionType.CREATE_LABEL,
                PhaseType.LABELS_AND_MILESTONES,
                f"Create label: {label['name']}",
                {
                    "name": label["name"],
                    "color": label.get("color", "cccccc"),
                    "description": label.get("description", ""),
                },
                entity_id=f"label_{label['name']}",
                dependencies=[repo_action]
            )
            label_actions.append(label_action)
        
        milestone_actions = []
        for milestone in transform_output.get("milestones", []):
            milestone_action = self.add_action(
                ActionType.CREATE_MILESTONE,
                PhaseType.LABELS_AND_MILESTONES,
                f"Create milestone: {milestone['title']}",
                {
                    "title": milestone["title"],
                    "description": milestone.get("description", ""),
                    "due_date": milestone.get("due_date"),
                },
                entity_id=f"milestone_{milestone['id']}",
                dependencies=[repo_action]
            )
            milestone_actions.append(milestone_action)
        
        # Phase 4: Issues and PRs
        issue_actions = []
        for issue in transform_output.get("issues", []):
            issue_action = self.add_action(
                ActionType.CREATE_ISSUE,
                PhaseType.ISSUES_AND_PRS,
                f"Create issue #{issue['number']}: {issue['title']}",
                {
                    "title": issue["title"],
                    "body": issue.get("body", ""),
                    "labels": issue.get("labels", []),
                    "milestone": issue.get("milestone"),
                    "assignees": issue.get("assignees", []),
                },
                entity_id=f"issue_{issue['number']}",
                dependencies=[repo_action] + label_actions + milestone_actions
            )
            issue_actions.append((issue['number'], issue_action))
            
            # Add comments
            for comment in issue.get("comments", []):
                self.add_action(
                    ActionType.ADD_ISSUE_COMMENT,
                    PhaseType.ISSUES_AND_PRS,
                    f"Add comment to issue #{issue['number']}",
                    {
                        "issue_number": issue["number"],
                        "body": comment["body"],
                        "author": comment.get("author"),
                        "created_at": comment.get("created_at"),
                    },
                    entity_id=f"issue_comment_{issue['number']}_{comment['id']}",
                    dependencies=[issue_action]
                )
        
        pr_actions = []
        for pr in transform_output.get("pull_requests", []):
            pr_action = self.add_action(
                ActionType.CREATE_PULL_REQUEST,
                PhaseType.ISSUES_AND_PRS,
                f"Create PR #{pr['number']}: {pr['title']}",
                {
                    "title": pr["title"],
                    "body": pr.get("body", ""),
                    "head": pr["head"],
                    "base": pr["base"],
                    "labels": pr.get("labels", []),
                },
                entity_id=f"pr_{pr['number']}",
                dependencies=[code_action] + label_actions
            )
            pr_actions.append(pr_action)
            
            # Add PR comments
            for comment in pr.get("comments", []):
                self.add_action(
                    ActionType.ADD_PR_COMMENT,
                    PhaseType.ISSUES_AND_PRS,
                    f"Add comment to PR #{pr['number']}",
                    {
                        "pr_number": pr["number"],
                        "body": comment["body"],
                        "commit_id": comment.get("commit_id"),
                        "path": comment.get("path"),
                        "position": comment.get("position"),
                    },
                    entity_id=f"pr_comment_{pr['number']}_{comment['id']}",
                    dependencies=[pr_action]
                )
        
        # Phase 5: CI/CD Setup
        for workflow in transform_output.get("workflows", []):
            workflow_action = self.add_action(
                ActionType.COMMIT_WORKFLOW,
                PhaseType.CICD_SETUP,
                f"Commit workflow: {workflow['name']}",
                {
                    "name": workflow["name"],
                    "path": workflow["path"],
                    "content": workflow["content"],
                },
                entity_id=f"workflow_{workflow['name']}",
                dependencies=[code_action]
            )
        
        # Environments, secrets, and variables
        for env in transform_output.get("environments", []):
            env_action = self.add_action(
                ActionType.CREATE_ENVIRONMENT,
                PhaseType.CICD_SETUP,
                f"Create environment: {env['name']}",
                {"name": env["name"]},
                entity_id=f"env_{env['name']}",
                dependencies=[repo_action],
                requires_user_input=True,
                user_input_fields=[{"name": "protection_rules", "description": "Environment protection rules"}]
            )
        
        for secret in transform_output.get("secrets", []):
            self.add_action(
                ActionType.SET_SECRET,
                PhaseType.CICD_SETUP,
                f"Set secret: {secret['name']}",
                {"name": secret["name"], "scope": secret.get("scope", "repository")},
                entity_id=f"secret_{secret['name']}",
                dependencies=[repo_action],
                requires_user_input=True,
                user_input_fields=[{"name": "value", "description": f"Value for secret {secret['name']}"}]
            )
        
        for variable in transform_output.get("variables", []):
            self.add_action(
                ActionType.SET_VARIABLE,
                PhaseType.CICD_SETUP,
                f"Set variable: {variable['name']}",
                {"name": variable["name"], "value": variable["value"]},
                entity_id=f"variable_{variable['name']}",
                dependencies=[repo_action]
            )
        
        # Phase 6: Wiki and Releases
        if transform_output.get("wiki", {}).get("enabled", False):
            wiki_action = self.add_action(
                ActionType.PUSH_WIKI,
                PhaseType.WIKI_AND_RELEASES,
                "Push wiki content",
                {"pages": transform_output.get("wiki", {}).get("pages", [])},
                entity_id="wiki",
                dependencies=[repo_action]
            )
        
        for release in transform_output.get("releases", []):
            release_action = self.add_action(
                ActionType.CREATE_RELEASE,
                PhaseType.WIKI_AND_RELEASES,
                f"Create release: {release['tag_name']}",
                {
                    "tag_name": release["tag_name"],
                    "name": release.get("name", release["tag_name"]),
                    "body": release.get("body", ""),
                    "draft": release.get("draft", False),
                    "prerelease": release.get("prerelease", False),
                },
                entity_id=f"release_{release['tag_name']}",
                dependencies=[code_action]
            )
            
            # Upload release assets
            for asset in release.get("assets", []):
                self.add_action(
                    ActionType.UPLOAD_RELEASE_ASSET,
                    PhaseType.WIKI_AND_RELEASES,
                    f"Upload asset: {asset['name']} to release {release['tag_name']}",
                    {
                        "release_tag": release["tag_name"],
                        "name": asset["name"],
                        "path": asset["path"],
                    },
                    entity_id=f"asset_{release['tag_name']}_{asset['name']}",
                    dependencies=[release_action]
                )
        
        # Phase 7: Settings and Permissions
        for protection in transform_output.get("branch_protections", []):
            self.add_action(
                ActionType.SET_BRANCH_PROTECTION,
                PhaseType.SETTINGS_AND_PERMISSIONS,
                f"Set branch protection for: {protection['branch']}",
                {
                    "branch": protection["branch"],
                    "required_reviews": protection.get("required_reviews", 1),
                    "require_code_owner_reviews": protection.get("require_code_owner_reviews", False),
                    "dismiss_stale_reviews": protection.get("dismiss_stale_reviews", False),
                    "require_status_checks": protection.get("require_status_checks", []),
                },
                entity_id=f"protection_{protection['branch']}",
                dependencies=[code_action]
            )
        
        for collaborator in transform_output.get("collaborators", []):
            self.add_action(
                ActionType.ADD_COLLABORATOR,
                PhaseType.SETTINGS_AND_PERMISSIONS,
                f"Add collaborator: {collaborator['username']}",
                {
                    "username": collaborator["username"],
                    "permission": collaborator.get("permission", "push"),
                },
                entity_id=f"collaborator_{collaborator['username']}",
                dependencies=[repo_action]
            )
        
        for webhook in transform_output.get("webhooks", []):
            self.add_action(
                ActionType.CREATE_WEBHOOK,
                PhaseType.SETTINGS_AND_PERMISSIONS,
                f"Create webhook: {webhook['url']}",
                {
                    "url": webhook["url"],
                    "events": webhook.get("events", ["push"]),
                    "content_type": webhook.get("content_type", "json"),
                },
                entity_id=f"webhook_{hashlib.md5(webhook['url'].encode()).hexdigest()[:8]}",
                dependencies=[repo_action],
                requires_user_input=True,
                user_input_fields=[{"name": "secret", "description": "Webhook secret"}]
            )
        
        # Phase 8: Preservation Artifacts
        if transform_output.get("preservation_artifacts"):
            self.add_action(
                ActionType.COMMIT_PRESERVATION_ARTIFACTS,
                PhaseType.PRESERVATION_ARTIFACTS,
                "Commit preservation artifacts",
                {
                    "artifacts": transform_output.get("preservation_artifacts", {}),
                    "branch": ".gitlab-archive",
                },
                entity_id="preservation",
                dependencies=[code_action]
            )
        
        return self.build_plan()
    
    def build_plan(self) -> Plan:
        """
        Build the final plan with sorted actions and phase organization.
        
        Returns:
            Complete migration plan
        """
        # Validate and sort actions
        is_valid, cycle = self.dependency_graph.validate_no_cycles()
        if not is_valid:
            raise ValueError(f"Circular dependency detected: {' -> '.join(cycle)}")
        
        sorted_action_ids = self.dependency_graph.topological_sort()
        
        # Reorder actions according to topological sort
        action_map = {action["id"]: action for action in self.actions}
        sorted_actions = [action_map[action_id] for action_id in sorted_action_ids]
        
        # Organize by phase
        phases: dict[str, list[str]] = {}
        for phase_type in PhaseType:
            phases[phase_type.value] = []
        
        for action in sorted_actions:
            phases[action["phase"]].append(action["id"])
        
        # Calculate statistics
        stats = {
            "total_actions": len(sorted_actions),
            "actions_by_type": {},
            "actions_by_phase": {},
            "actions_requiring_user_input": 0,
            "total_dependencies": sum(len(action.get("dependencies", [])) for action in sorted_actions),
        }
        
        for action in sorted_actions:
            action_type = action["action_type"]
            stats["actions_by_type"][action_type] = stats["actions_by_type"].get(action_type, 0) + 1
            
            phase = action["phase"]
            stats["actions_by_phase"][phase] = stats["actions_by_phase"].get(phase, 0) + 1
            
            if action.get("requires_user_input", False):
                stats["actions_requiring_user_input"] += 1
        
        plan: Plan = {
            "version": "1.0",
            "project_id": self.project_id,
            "run_id": self.run_id,
            "generated_at": datetime.now(datetime.UTC if hasattr(datetime, 'UTC') else timezone.utc).isoformat(),
            "actions": sorted_actions,
            "phases": phases,
            "statistics": stats,
        }
        
        return plan
    
    def get_user_inputs_required(self) -> list[dict[str, Any]]:
        """
        Get list of actions requiring user input.
        
        Returns:
            List of action summaries requiring user input
        """
        return [
            {
                "action_id": action["id"],
                "action_type": action["action_type"],
                "description": action["description"],
                "user_input_fields": action.get("user_input_fields", []),
            }
            for action in self.actions
            if action.get("requires_user_input", False)
        ]
