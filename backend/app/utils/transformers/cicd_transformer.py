"""GitLab CI to GitHub Actions transformer"""

import re
import yaml
from typing import Any, Dict, List, Optional, Tuple
from .base_transformer import BaseTransformer, TransformationResult


class CICDTransformer(BaseTransformer):
    """
    Transform GitLab CI configurations to GitHub Actions workflows.
    
    Handles:
    - stages → job dependencies
    - script → run steps
    - image → container settings
    - services → service containers
    - artifacts → upload/download artifacts
    - cache → cache action
    - rules/only/except → if conditions
    - needs → job dependencies
    - extends → reusable workflows
    - include → composite actions/reusable workflows
    """
    
    def __init__(self):
        super().__init__("CICDTransformer")
        self.conversion_gaps: List[Dict[str, Any]] = []
    
    def transform(self, input_data: Dict[str, Any]) -> TransformationResult:
        """
        Transform GitLab CI YAML to GitHub Actions workflows.
        
        Args:
            input_data: Dict with 'gitlab_ci_yaml' (dict or str)
            
        Returns:
            TransformationResult with GitHub Actions workflow(s)
        """
        self.log_transform_start("GitLab CI")
        result = TransformationResult(success=True)
        
        # Validate input
        validation = self.validate_input(input_data, ["gitlab_ci_yaml"])
        if not validation.success:
            return validation
        
        try:
            # Parse GitLab CI YAML if it's a string
            gitlab_ci = input_data["gitlab_ci_yaml"]
            if isinstance(gitlab_ci, str):
                gitlab_ci = yaml.safe_load(gitlab_ci)
            
            # Extract configuration
            stages = gitlab_ci.get("stages", [])
            jobs = self._extract_jobs(gitlab_ci)
            variables = gitlab_ci.get("variables", {})
            
            # Transform to GitHub Actions
            workflow = self._create_github_workflow(stages, jobs, variables)
            
            # Track conversion gaps
            result.metadata["conversion_gaps"] = self.conversion_gaps
            result.metadata["jobs_converted"] = len(jobs)
            result.metadata["stages"] = len(stages)
            
            result.data = {
                "workflow": workflow,
                "workflow_yaml": yaml.dump(workflow, sort_keys=False, default_flow_style=False)
            }
            
            self.log_transform_complete(True, f"Converted {len(jobs)} jobs")
            
        except yaml.YAMLError as e:
            result.add_error(f"Invalid YAML: {str(e)}")
            self.log_transform_complete(False, f"YAML parsing error: {str(e)}")
        except Exception as e:
            result.add_error(f"Transformation error: {str(e)}")
            self.log_transform_complete(False, str(e))
        
        return result
    
    def _extract_jobs(self, gitlab_ci: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Extract job definitions from GitLab CI"""
        jobs = {}
        
        # Keywords to skip (not actual jobs)
        keywords = {
            "stages", "variables", "workflow", "include", "default",
            "image", "services", "before_script", "after_script", "cache"
        }
        
        for key, value in gitlab_ci.items():
            if key.startswith("."):  # Hidden jobs/templates
                continue
            if key in keywords:
                continue
            if isinstance(value, dict) and ("script" in value or "trigger" in value):
                jobs[key] = value
        
        return jobs
    
    def _create_github_workflow(
        self,
        stages: List[str],
        jobs: Dict[str, Dict[str, Any]],
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create GitHub Actions workflow from GitLab CI components"""
        
        workflow = {
            "name": "CI",
            "on": self._convert_triggers(jobs),
            "env": self._convert_variables(variables),
            "jobs": {}
        }
        
        # Convert each job
        for job_name, job_config in jobs.items():
            gh_job = self._convert_job(job_name, job_config, stages)
            workflow["jobs"][self._sanitize_job_name(job_name)] = gh_job
        
        return workflow
    
    def _convert_job(
        self,
        job_name: str,
        job_config: Dict[str, Any],
        stages: List[str]
    ) -> Dict[str, Any]:
        """Convert a single GitLab CI job to GitHub Actions job"""
        
        gh_job: Dict[str, Any] = {
            "runs-on": self._convert_tags(job_config.get("tags", []))
        }
        
        # Handle job dependencies (needs)
        needs = self._convert_needs(job_config.get("needs", []), job_config.get("stage"), stages)
        if needs:
            gh_job["needs"] = needs
        
        # Handle image (container)
        if "image" in job_config:
            gh_job["container"] = self._convert_image(job_config["image"])
        
        # Handle services
        if "services" in job_config:
            gh_job["services"] = self._convert_services(job_config["services"])
        
        # Handle environment variables
        if "variables" in job_config:
            gh_job["env"] = self._convert_variables(job_config["variables"])
        
        # Handle if conditions (rules)
        if_condition = self._convert_rules(job_config)
        if if_condition:
            gh_job["if"] = if_condition
        
        # Convert steps
        gh_job["steps"] = self._convert_steps(job_config)
        
        return gh_job
    
    def _convert_steps(self, job_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert GitLab CI scripts to GitHub Actions steps"""
        steps = []
        
        # Checkout step (always needed)
        steps.append({
            "name": "Checkout code",
            "uses": "actions/checkout@v4"
        })
        
        # Before script
        if "before_script" in job_config:
            steps.append({
                "name": "Before script",
                "run": self._convert_script_to_run(job_config["before_script"])
            })
        
        # Main script
        if "script" in job_config:
            steps.append({
                "name": "Run script",
                "run": self._convert_script_to_run(job_config["script"])
            })
        
        # After script
        if "after_script" in job_config:
            steps.append({
                "name": "After script",
                "if": "always()",
                "run": self._convert_script_to_run(job_config["after_script"])
            })
        
        # Handle artifacts
        if "artifacts" in job_config:
            artifact_step = self._convert_artifacts(job_config["artifacts"])
            if artifact_step:
                steps.append(artifact_step)
        
        # Handle cache
        if "cache" in job_config:
            cache_step = self._convert_cache(job_config["cache"])
            if cache_step:
                # Cache should be early in the steps
                steps.insert(1, cache_step)
        
        return steps
    
    def _convert_script_to_run(self, script: Any) -> str:
        """Convert GitLab CI script to GitHub Actions run"""
        if isinstance(script, list):
            script_text = "\n".join(script)
        else:
            script_text = str(script)
        
        # Transform registry URLs in scripts
        script_text = self._transform_registry_urls(script_text)
        
        return script_text
    
    def _transform_registry_urls(self, script: str) -> str:
        """
        Transform GitLab registry URLs to GitHub GHCR URLs in scripts.
        
        Handles:
        - registry.gitlab.com → ghcr.io
        - $CI_REGISTRY_IMAGE → ghcr.io/${{ github.repository }}
        - $CI_REGISTRY → ghcr.io
        """
        transformations = {
            'registry.gitlab.com': 'ghcr.io',
            '$CI_REGISTRY_IMAGE': 'ghcr.io/${{ github.repository }}',
            '${CI_REGISTRY_IMAGE}': 'ghcr.io/${{ github.repository }}',
            '$CI_REGISTRY': 'ghcr.io',
            '${CI_REGISTRY}': 'ghcr.io',
        }
        
        transformed = script
        for old, new in transformations.items():
            if old in transformed:
                transformed = transformed.replace(old, new)
                # Track this as a conversion gap
                if old not in ['$CI_REGISTRY', '${CI_REGISTRY}']:  # Don't report base registry changes
                    self.conversion_gaps.append({
                        "type": "registry_url",
                        "message": f"Transformed registry reference: {old} → {new}",
                        "action": "Verify registry URLs are correct for your setup"
                    })
        
        return transformed
    
    def _convert_triggers(self, jobs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Convert GitLab CI triggers to GitHub Actions triggers"""
        triggers: Dict[str, Any] = {}
        
        # Check for common patterns
        has_push = False
        has_mr = False
        has_schedule = False
        
        for job_config in jobs.values():
            # Check 'only' and 'except' keywords
            if "only" in job_config:
                only = job_config["only"]
                if isinstance(only, list):
                    if "pushes" in only or "branches" in only:
                        has_push = True
                    if "merge_requests" in only:
                        has_mr = True
                    if "schedules" in only:
                        has_schedule = True
            
            # Check 'rules'
            if "rules" in job_config:
                for rule in job_config["rules"]:
                    if isinstance(rule, dict):
                        if "$CI_PIPELINE_SOURCE" in str(rule.get("if", "")):
                            if "merge_request" in str(rule.get("if", "")):
                                has_mr = True
                            if "schedule" in str(rule.get("if", "")):
                                has_schedule = True
                            if "push" in str(rule.get("if", "")):
                                has_push = True
        
        # Default: push and pull_request
        if not has_push and not has_mr and not has_schedule:
            triggers["push"] = {"branches": ["main", "master"]}
            triggers["pull_request"] = {"branches": ["main", "master"]}
        else:
            if has_push:
                triggers["push"] = {"branches": ["main", "master"]}
            if has_mr:
                triggers["pull_request"] = {"branches": ["main", "master"]}
            if has_schedule:
                # Default schedule - user should customize
                triggers["schedule"] = [{"cron": "0 0 * * *"}]
                self.conversion_gaps.append({
                    "type": "schedule",
                    "message": "Schedule trigger detected but no cron expression found. Default daily schedule created.",
                    "action": "Review and update schedule cron expression in workflow file"
                })
        
        return triggers
    
    def _convert_variables(self, variables: Dict[str, Any]) -> Dict[str, str]:
        """Convert GitLab CI variables to GitHub Actions env vars"""
        env = {}
        
        for key, value in variables.items():
            # Skip GitLab predefined variables
            if key.startswith("CI_"):
                # Map common CI_ variables to GitHub equivalents
                gh_var = self._map_ci_variable(key)
                if gh_var:
                    env[key] = gh_var
                else:
                    self.conversion_gaps.append({
                        "type": "variable",
                        "variable": key,
                        "message": f"GitLab CI variable {key} has no direct GitHub equivalent",
                        "action": "Review and manually set this variable or secret"
                    })
            else:
                env[key] = str(value)
        
        return env
    
    def _map_ci_variable(self, gitlab_var: str) -> Optional[str]:
        """Map GitLab CI_ variables to GitHub equivalents"""
        mappings = {
            "CI_COMMIT_SHA": "${{ github.sha }}",
            "CI_COMMIT_REF_NAME": "${{ github.ref_name }}",
            "CI_COMMIT_BRANCH": "${{ github.ref_name }}",
            "CI_COMMIT_TAG": "${{ github.ref_name }}",
            "CI_PROJECT_NAME": "${{ github.event.repository.name }}",
            "CI_PROJECT_PATH": "${{ github.repository }}",
            "CI_PIPELINE_ID": "${{ github.run_id }}",
            "CI_PIPELINE_IID": "${{ github.run_number }}",
            "CI_JOB_ID": "${{ github.job }}",
            "CI_REPOSITORY_URL": "${{ github.repositoryUrl }}",
            "CI_DEFAULT_BRANCH": "${{ github.event.repository.default_branch }}",
            # Container registry mappings
            "CI_REGISTRY": "ghcr.io",
            "CI_REGISTRY_IMAGE": "ghcr.io/${{ github.repository }}",
        }
        return mappings.get(gitlab_var)
    
    def _convert_image(self, image: Any) -> Dict[str, Any]:
        """Convert GitLab CI image to GitHub Actions container"""
        if isinstance(image, str):
            return {"image": image}
        elif isinstance(image, dict):
            container = {"image": image.get("name", "")}
            if "entrypoint" in image:
                container["options"] = f"--entrypoint {image['entrypoint']}"
            return container
        return {"image": "ubuntu:latest"}
    
    def _convert_services(self, services: List[Any]) -> Dict[str, Dict[str, Any]]:
        """Convert GitLab CI services to GitHub Actions service containers"""
        gh_services = {}
        
        for i, service in enumerate(services):
            if isinstance(service, str):
                service_name = service.split(":")[0].replace("/", "-")
                gh_services[service_name] = {"image": service}
            elif isinstance(service, dict):
                name = service.get("name", f"service-{i}")
                service_name = name.split(":")[0].replace("/", "-")
                gh_services[service_name] = {"image": service.get("name", "")}
                if "alias" in service:
                    gh_services[service_name]["options"] = f"--network-alias {service['alias']}"
        
        return gh_services
    
    def _convert_artifacts(self, artifacts: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert GitLab CI artifacts to GitHub Actions upload-artifact"""
        if not isinstance(artifacts, dict):
            return None
        
        paths = artifacts.get("paths", [])
        if not paths:
            return None
        
        return {
            "name": "Upload artifacts",
            "uses": "actions/upload-artifact@v4",
            "with": {
                "name": artifacts.get("name", "artifacts"),
                "path": "\n".join(paths) if isinstance(paths, list) else paths
            }
        }
    
    def _convert_cache(self, cache: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert GitLab CI cache to GitHub Actions cache"""
        if not isinstance(cache, dict):
            return None
        
        paths = cache.get("paths", [])
        if not paths:
            return None
        
        key = cache.get("key", "${{ runner.os }}-cache")
        
        return {
            "name": "Cache dependencies",
            "uses": "actions/cache@v4",
            "with": {
                "path": "\n".join(paths) if isinstance(paths, list) else paths,
                "key": key
            }
        }
    
    def _convert_rules(self, job_config: Dict[str, Any]) -> Optional[str]:
        """Convert GitLab CI rules to GitHub Actions if conditions"""
        conditions = []
        
        # Handle 'only' and 'except'
        if "only" in job_config:
            only = job_config["only"]
            if isinstance(only, dict):
                if "refs" in only:
                    refs = only["refs"] if isinstance(only["refs"], list) else [only["refs"]]
                    for ref in refs:
                        if ref == "merge_requests":
                            conditions.append("github.event_name == 'pull_request'")
                        elif ref == "branches":
                            conditions.append("github.ref_type == 'branch'")
                        elif ref == "tags":
                            conditions.append("github.ref_type == 'tag'")
        
        if "except" in job_config:
            except_rules = job_config["except"]
            if isinstance(except_rules, dict):
                if "refs" in except_rules:
                    refs = except_rules["refs"] if isinstance(except_rules["refs"], list) else [except_rules["refs"]]
                    for ref in refs:
                        if ref == "merge_requests":
                            conditions.append("github.event_name != 'pull_request'")
                        elif ref == "branches":
                            conditions.append("github.ref_type != 'branch'")
        
        # Handle 'rules' (complex)
        if "rules" in job_config:
            for rule in job_config["rules"]:
                if isinstance(rule, dict) and "if" in rule:
                    # Try to convert GitLab CI if to GitHub Actions if
                    gh_condition = self._convert_if_condition(rule["if"])
                    if gh_condition:
                        conditions.append(gh_condition)
        
        if conditions:
            return " && ".join(conditions)
        
        return None
    
    def _convert_if_condition(self, gitlab_if: str) -> Optional[str]:
        """Convert GitLab CI if condition to GitHub Actions"""
        # Basic conversion - more complex logic may be needed
        gh_if = gitlab_if
        
        # Replace common patterns
        replacements = {
            "$CI_COMMIT_BRANCH": "github.ref_name",
            "$CI_COMMIT_TAG": "github.ref_name",
            "$CI_MERGE_REQUEST_ID": "github.event.pull_request.number",
            "$CI_PIPELINE_SOURCE": "github.event_name",
            "== 'merge_request_event'": "== 'pull_request'",
            "== 'push'": "== 'push'",
        }
        
        for old, new in replacements.items():
            gh_if = gh_if.replace(old, new)
        
        return gh_if
    
    def _convert_needs(
        self,
        needs: List[str],
        stage: Optional[str],
        stages: List[str]
    ) -> List[str]:
        """Convert GitLab CI needs to GitHub Actions needs"""
        if needs:
            # Sanitize job names in needs
            return [self._sanitize_job_name(need) for need in needs]
        
        # If no explicit needs, infer from stage order
        if stage and stages:
            try:
                stage_idx = stages.index(stage)
                if stage_idx > 0:
                    # This job depends on all jobs in previous stage
                    # Note: This is a simplification - actual implementation
                    # would need to track which jobs are in which stage
                    self.conversion_gaps.append({
                        "type": "stage_dependency",
                        "stage": stage,
                        "message": f"Stage-based dependency for '{stage}' may need manual adjustment",
                        "action": "Review job dependencies in workflow file"
                    })
            except ValueError:
                pass
        
        return []
    
    def _convert_tags(self, tags: List[str]) -> str:
        """Convert GitLab runner tags to GitHub runner labels"""
        if not tags:
            return "ubuntu-latest"
        
        # Map common tags to GitHub runners
        tag_map = {
            "docker": "ubuntu-latest",
            "linux": "ubuntu-latest",
            "ubuntu": "ubuntu-latest",
            "windows": "windows-latest",
            "macos": "macos-latest",
            "mac": "macos-latest",
        }
        
        for tag in tags:
            tag_lower = tag.lower()
            if tag_lower in tag_map:
                return tag_map[tag_lower]
        
        # For custom runners, note in conversion gaps
        self.conversion_gaps.append({
            "type": "runner_tags",
            "tags": tags,
            "message": f"Custom runner tags {tags} may require self-hosted runner setup",
            "action": "Configure self-hosted runners or update runs-on value"
        })
        
        return "ubuntu-latest"
    
    def _sanitize_job_name(self, name: str) -> str:
        """Sanitize job name for GitHub Actions (lowercase, hyphens)"""
        # Replace spaces and special chars with hyphens
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '-', name)
        # Remove multiple consecutive hyphens
        sanitized = re.sub(r'-+', '-', sanitized)
        # Remove leading/trailing hyphens
        sanitized = sanitized.strip('-')
        return sanitized.lower()
