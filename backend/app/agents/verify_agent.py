"""Verify Agent - Validate migration results using Microsoft Agent Framework"""

from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import json
import re
import base64
import httpx
import yaml
from datetime import datetime
from app.agents.base_agent import BaseAgent, AgentResult
from app.utils.logging import get_logger

logger = get_logger(__name__)


class VerificationResult:
    """Container for verification results"""
    
    def __init__(self, component: str):
        self.component = component
        self.status = "pending"  # pending, success, warning, error
        self.checks = []
        self.discrepancies = []
        self.warnings = []
        self.errors = []
        self.stats = {}
    
    def add_check(self, name: str, passed: bool, details: Optional[Dict] = None):
        """Add a verification check"""
        self.checks.append({
            "name": name,
            "passed": passed,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat()
        })
        
    def add_discrepancy(self, message: str, severity: str, details: Optional[Dict] = None):
        """Add a discrepancy found during verification"""
        discrepancy = {
            "message": message,
            "severity": severity,  # error, warning, info
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if severity == "error":
            self.errors.append(discrepancy)
        elif severity == "warning":
            self.warnings.append(discrepancy)
        else:
            self.discrepancies.append(discrepancy)
    
    def set_status(self):
        """Determine overall status based on checks and discrepancies"""
        if self.errors:
            self.status = "error"
        elif self.warnings:
            self.status = "warning"
        elif any(not check["passed"] for check in self.checks):
            self.status = "error"
        else:
            self.status = "success"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "component": self.component,
            "status": self.status,
            "checks": self.checks,
            "discrepancies": self.discrepancies,
            "warnings": self.warnings,
            "errors": self.errors,
            "stats": self.stats
        }


class VerifyAgent(BaseAgent):
    """
    Verify Agent for validating migration success.
    
    Using Microsoft Agent Framework patterns:
    - Comprehensive validation checks
    - Tool integration (GitHub API, git commands)
    - Structured reporting
    - Detailed failure analysis
    """
    
    def __init__(self):
        super().__init__(
            agent_name="VerifyAgent",
            instructions="""
            You are specialized in verifying migration completeness and correctness.
            Your responsibilities:
            1. Verify repository exists and is accessible
            2. Check commit/branch/tag parity with source
            3. Validate workflow files syntax
            4. Verify environments and secrets presence
            5. Check issues and pull requests imported
            6. Validate wiki pages
            7. Verify releases and packages
            8. Verify settings and configurations
            9. Verify preservation artifacts
            
            Generate detailed verification reports.
            Identify and categorize any discrepancies.
            Provide recommendations for remediation.
            """
        )
        self.github_client = None
        self.gitlab_client = None
    
    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        """Validate verify inputs"""
        required = ["github_token", "github_repo", "expected_state", "output_dir"]
        if not all(field in inputs for field in required):
            return False
        
        # github_repo should be in format "owner/repo"
        if "/" not in inputs["github_repo"]:
            return False
        
        return True
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute verification"""
        self.log_event("INFO", f"Starting verification for {inputs['github_repo']}")
        
        try:
            # Initialize API clients
            timeout = inputs.get("timeout", 60.0)  # Configurable timeout, default 60s
            self.github_client = httpx.AsyncClient(
                base_url="https://api.github.com",
                headers={
                    "Authorization": f"Bearer {inputs['github_token']}",  # Modern format
                    "Accept": "application/vnd.github.v3+json"
                },
                timeout=timeout
            )
            
            # Initialize GitLab client if provided
            if inputs.get("gitlab_token") and inputs.get("gitlab_url"):
                self.gitlab_client = httpx.AsyncClient(
                    base_url=inputs["gitlab_url"],
                    headers={
                        "Authorization": f"Bearer {inputs['gitlab_token']}",
                        "Accept": "application/json"
                    },
                    timeout=30.0
                )
            
            output_dir = Path(inputs["output_dir"])
            verify_dir = output_dir / "verify"
            verify_dir.mkdir(parents=True, exist_ok=True)
            
            expected_state = inputs["expected_state"]
            github_repo = inputs["github_repo"]
            
            # Execute all verification checks
            verification_results = {}
            all_discrepancies = []
            
            # 1. Repository verification
            self.log_event("INFO", "Verifying repository...")
            repo_result = await self._verify_repository(github_repo, expected_state.get("repository", {}))
            verification_results["repository"] = repo_result.to_dict()
            all_discrepancies.extend(repo_result.errors + repo_result.warnings)
            
            # 2. CI/CD verification
            self.log_event("INFO", "Verifying CI/CD...")
            cicd_result = await self._verify_cicd(github_repo, expected_state.get("ci_cd", {}))
            verification_results["ci_cd"] = cicd_result.to_dict()
            all_discrepancies.extend(cicd_result.errors + cicd_result.warnings)
            
            # 3. Issues verification
            self.log_event("INFO", "Verifying issues...")
            issues_result = await self._verify_issues(github_repo, expected_state.get("issues", {}))
            verification_results["issues"] = issues_result.to_dict()
            all_discrepancies.extend(issues_result.errors + issues_result.warnings)
            
            # 4. Pull requests verification
            self.log_event("INFO", "Verifying pull requests...")
            pr_result = await self._verify_pull_requests(github_repo, expected_state.get("pull_requests", {}))
            verification_results["pull_requests"] = pr_result.to_dict()
            all_discrepancies.extend(pr_result.errors + pr_result.warnings)
            
            # 5. Wiki verification
            self.log_event("INFO", "Verifying wiki...")
            wiki_result = await self._verify_wiki(github_repo, expected_state.get("wiki", {}))
            verification_results["wiki"] = wiki_result.to_dict()
            all_discrepancies.extend(wiki_result.errors + wiki_result.warnings)
            
            # 6. Releases verification
            self.log_event("INFO", "Verifying releases...")
            releases_result = await self._verify_releases(github_repo, expected_state.get("releases", {}))
            verification_results["releases"] = releases_result.to_dict()
            all_discrepancies.extend(releases_result.errors + releases_result.warnings)
            
            # 7. Packages verification
            self.log_event("INFO", "Verifying packages...")
            packages_result = await self._verify_packages(github_repo, expected_state.get("packages", {}))
            verification_results["packages"] = packages_result.to_dict()
            all_discrepancies.extend(packages_result.errors + packages_result.warnings)
            
            # 8. Settings verification
            self.log_event("INFO", "Verifying settings...")
            settings_result = await self._verify_settings(github_repo, expected_state.get("settings", {}))
            verification_results["settings"] = settings_result.to_dict()
            all_discrepancies.extend(settings_result.errors + settings_result.warnings)
            
            # 9. Preservation verification
            self.log_event("INFO", "Verifying preservation artifacts...")
            preservation_result = await self._verify_preservation(github_repo, expected_state.get("preservation", {}))
            verification_results["preservation"] = preservation_result.to_dict()
            all_discrepancies.extend(preservation_result.errors + preservation_result.warnings)
            
            # Generate reports
            verify_report = self._generate_verify_report(verification_results, all_discrepancies)
            verify_summary = self._generate_verify_summary(verification_results, all_discrepancies)
            component_status = self._generate_component_status(verification_results)
            discrepancies_report = self._generate_discrepancies_report(all_discrepancies)
            
            # Save artifacts
            artifacts = []
            
            report_path = verify_dir / "verify_report.json"
            with open(report_path, "w") as f:
                json.dump(verify_report, f, indent=2)
            artifacts.append(str(report_path))
            
            summary_path = verify_dir / "verify_summary.md"
            with open(summary_path, "w") as f:
                f.write(verify_summary)
            artifacts.append(str(summary_path))
            
            status_path = verify_dir / "component_status.json"
            with open(status_path, "w") as f:
                json.dump(component_status, f, indent=2)
            artifacts.append(str(status_path))
            
            discrepancies_path = verify_dir / "discrepancies.json"
            with open(discrepancies_path, "w") as f:
                json.dump(discrepancies_report, f, indent=2)
            artifacts.append(str(discrepancies_path))
            
            # Determine overall status
            errors = [d for d in all_discrepancies if d.get("severity") == "error"]
            warnings = [d for d in all_discrepancies if d.get("severity") == "warning"]
            
            overall_status = "success"
            if errors:
                overall_status = "failed"
            elif warnings:
                overall_status = "partial"
            
            self.log_event("INFO", f"Verification complete: {overall_status}", {
                "errors": len(errors),
                "warnings": len(warnings)
            })
            
            return AgentResult(
                status=overall_status,
                outputs={
                    "verification_results": verification_results,
                    "verify_complete": True,
                    "total_errors": len(errors),
                    "total_warnings": len(warnings),
                    "components_verified": len(verification_results)
                },
                artifacts=artifacts,
                errors=errors
            ).to_dict()
            
        except Exception as e:
            self.log_event("ERROR", f"Verification failed: {str(e)}")
            return AgentResult(
                status="failed",
                outputs={},
                artifacts=[],
                errors=[{"step": "verify", "message": str(e), "severity": "error"}]
            ).to_dict()
        finally:
            # Close API clients
            if self.github_client:
                await self.github_client.aclose()
            if self.gitlab_client:
                await self.gitlab_client.aclose()
    
    def _extract_page_count_from_link_header(self, link_header: str) -> Optional[int]:
        """Extract the last page number from a GitHub API Link header"""
        if not link_header:
            return None
        
        match = re.search(r'page=(\d+)>; rel="last"', link_header)
        if match:
            return int(match.group(1))
        return None
    
    def _is_within_tolerance(self, expected: int, actual: int, tolerance: float = 0.05) -> bool:
        """Check if actual value is within tolerance of expected value"""
        if expected == 0:
            return actual == 0
        
        diff = abs(actual - expected)
        max_diff = expected * tolerance
        return diff <= max_diff
    
    async def _verify_repository(self, repo: str, expected: Dict) -> VerificationResult:
        """Verify repository structure and content"""
        result = VerificationResult("repository")
        
        try:
            # Check if repository exists and is accessible
            response = await self.github_client.get(f"/repos/{repo}")
            if response.status_code != 200:
                result.add_discrepancy(
                    f"Repository not accessible: {response.status_code}",
                    "error",
                    {"status_code": response.status_code}
                )
                result.set_status()
                return result
            
            repo_data = response.json()
            result.add_check("repository_exists", True, {"name": repo_data.get("full_name")})
            
            # Verify branches
            branches_response = await self.github_client.get(f"/repos/{repo}/branches")
            if branches_response.status_code == 200:
                branches = branches_response.json()
                branch_count = len(branches)
                expected_branches = expected.get("branch_count", 0)
                
                result.stats["branch_count"] = branch_count
                result.add_check("branches_migrated", True, {"count": branch_count})
                
                if expected_branches > 0 and branch_count != expected_branches:
                    result.add_discrepancy(
                        f"Branch count mismatch: expected {expected_branches}, got {branch_count}",
                        "warning",
                        {"expected": expected_branches, "actual": branch_count}
                    )
            
            # Verify tags
            tags_response = await self.github_client.get(f"/repos/{repo}/tags")
            if tags_response.status_code == 200:
                tags = tags_response.json()
                tag_count = len(tags)
                expected_tags = expected.get("tag_count", 0)
                
                result.stats["tag_count"] = tag_count
                result.add_check("tags_migrated", True, {"count": tag_count})
                
                if expected_tags > 0 and tag_count != expected_tags:
                    result.add_discrepancy(
                        f"Tag count mismatch: expected {expected_tags}, got {tag_count}",
                        "warning",
                        {"expected": expected_tags, "actual": tag_count}
                    )
            
            # Verify default branch
            default_branch = repo_data.get("default_branch")
            result.stats["default_branch"] = default_branch
            result.add_check("default_branch_set", True, {"branch": default_branch})
            
            # Verify commit count on default branch
            commits_response = await self.github_client.get(
                f"/repos/{repo}/commits",
                params={"sha": default_branch, "per_page": 1}
            )
            if commits_response.status_code == 200:
                # Get commit count from Link header if available
                link_header = commits_response.headers.get("Link", "")
                page_count = self._extract_page_count_from_link_header(link_header)
                
                if page_count:
                    commit_count = page_count
                    result.stats["commit_count"] = commit_count
                    result.add_check("commits_migrated", True, {"count": commit_count})
                else:
                    # Single page of results - check if empty or has commits
                    commits = commits_response.json()
                    commit_count = 1 if commits else 0
                    result.stats["commit_count"] = commit_count
                    result.add_check("commits_migrated", True, {"count": commit_count})
            
            # Check LFS if expected
            if expected.get("lfs_enabled"):
                # Check for .gitattributes
                content_response = await self.github_client.get(f"/repos/{repo}/contents/.gitattributes")
                lfs_configured = content_response.status_code == 200
                result.add_check("lfs_configured", lfs_configured)
                
                if not lfs_configured:
                    result.add_discrepancy("LFS expected but .gitattributes not found", "warning")
            
        except Exception as e:
            result.add_discrepancy(f"Repository verification failed: {str(e)}", "error")
        
        result.set_status()
        return result
    
    async def _verify_cicd(self, repo: str, expected: Dict) -> VerificationResult:
        """Verify CI/CD workflows and configuration"""
        result = VerificationResult("ci_cd")
        
        try:
            # Verify workflows exist
            workflows_response = await self.github_client.get(f"/repos/{repo}/actions/workflows")
            if workflows_response.status_code == 200:
                workflows_data = workflows_response.json()
                workflows = workflows_data.get("workflows", [])
                workflow_count = len(workflows)
                expected_count = expected.get("workflow_count", 0)
                
                result.stats["workflow_count"] = workflow_count
                result.add_check("workflows_exist", workflow_count > 0, {"count": workflow_count})
                
                if expected_count > 0 and workflow_count != expected_count:
                    result.add_discrepancy(
                        f"Workflow count mismatch: expected {expected_count}, got {workflow_count}",
                        "warning",
                        {"expected": expected_count, "actual": workflow_count}
                    )
                
                # Verify workflow files are valid YAML
                for workflow in workflows[:5]:  # Sample first 5
                    workflow_path = workflow.get("path")
                    if workflow_path:
                        content_response = await self.github_client.get(
                            f"/repos/{repo}/contents/{workflow_path}"
                        )
                        if content_response.status_code == 200:
                            import base64
                            content_data = content_response.json()
                            content = base64.b64decode(content_data.get("content", "")).decode("utf-8")
                            try:
                                yaml.safe_load(content)
                                result.add_check(f"workflow_valid_{workflow.get('name')}", True)
                            except yaml.YAMLError as e:
                                result.add_discrepancy(
                                    f"Invalid workflow YAML: {workflow.get('name')}",
                                    "error",
                                    {"path": workflow_path, "error": str(e)}
                                )
            
            # Verify environments
            environments_response = await self.github_client.get(f"/repos/{repo}/environments")
            if environments_response.status_code == 200:
                environments_data = environments_response.json()
                environments = environments_data.get("environments", [])
                env_count = len(environments)
                expected_envs = expected.get("environment_count", 0)
                
                result.stats["environment_count"] = env_count
                result.add_check("environments_created", True, {"count": env_count})
                
                if expected_envs > 0 and env_count != expected_envs:
                    result.add_discrepancy(
                        f"Environment count mismatch: expected {expected_envs}, got {env_count}",
                        "warning",
                        {"expected": expected_envs, "actual": env_count}
                    )
            
            # Verify secrets (presence only)
            secrets_response = await self.github_client.get(f"/repos/{repo}/actions/secrets")
            if secrets_response.status_code == 200:
                secrets_data = secrets_response.json()
                secret_count = secrets_data.get("total_count", 0)
                result.stats["secret_count"] = secret_count
                result.add_check("secrets_exist", True, {"count": secret_count})
            
            # Verify variables
            variables_response = await self.github_client.get(f"/repos/{repo}/actions/variables")
            if variables_response.status_code == 200:
                variables_data = variables_response.json()
                variable_count = variables_data.get("total_count", 0)
                result.stats["variable_count"] = variable_count
                result.add_check("variables_exist", True, {"count": variable_count})
            
        except Exception as e:
            result.add_discrepancy(f"CI/CD verification failed: {str(e)}", "error")
        
        result.set_status()
        return result
    
    async def _verify_issues(self, repo: str, expected: Dict) -> VerificationResult:
        """Verify issues migration"""
        result = VerificationResult("issues")
        
        try:
            # Get issue counts by state
            all_issues_response = await self.github_client.get(
                f"/repos/{repo}/issues",
                params={"state": "all", "per_page": 1}
            )
            
            if all_issues_response.status_code == 200:
                # Parse Link header for total count
                link_header = all_issues_response.headers.get("Link", "")
                page_count = self._extract_page_count_from_link_header(link_header)
                
                if page_count:
                    total_issues = page_count
                else:
                    # Single page - check if we have any issues
                    issues = all_issues_response.json()
                    total_issues = len(issues)
                
                result.stats["total_issues"] = total_issues
                expected_count = expected.get("issue_count", 0)
                
                result.add_check("issues_migrated", True, {"count": total_issues})
                
                if expected_count > 0:
                    # Calculate match percentage
                    if expected_count == 0 and total_issues == 0:
                        match_percentage = 100.0
                    elif expected_count > 0:
                        match_percentage = (total_issues / expected_count) * 100
                    else:
                        match_percentage = 0.0
                    
                    result.stats["match_percentage"] = round(match_percentage, 2)
                    
                    if not self._is_within_tolerance(expected_count, total_issues, 0.05):
                        result.add_discrepancy(
                            f"Issue count mismatch: expected {expected_count}, got {total_issues}",
                            "warning",
                            {"expected": expected_count, "actual": total_issues, "match_percentage": match_percentage}
                        )
            
            # Get open vs closed counts
            open_response = await self.github_client.get(
                f"/repos/{repo}/issues",
                params={"state": "open", "per_page": 1}
            )
            closed_response = await self.github_client.get(
                f"/repos/{repo}/issues",
                params={"state": "closed", "per_page": 1}
            )
            
            # Verify labels
            labels_response = await self.github_client.get(f"/repos/{repo}/labels")
            if labels_response.status_code == 200:
                labels = labels_response.json()
                label_count = len(labels)
                result.stats["label_count"] = label_count
                result.add_check("labels_created", True, {"count": label_count})
            
            # Verify milestones
            milestones_response = await self.github_client.get(f"/repos/{repo}/milestones", params={"state": "all"})
            if milestones_response.status_code == 200:
                milestones = milestones_response.json()
                milestone_count = len(milestones)
                result.stats["milestone_count"] = milestone_count
                result.add_check("milestones_created", True, {"count": milestone_count})
            
        except Exception as e:
            result.add_discrepancy(f"Issues verification failed: {str(e)}", "error")
        
        result.set_status()
        return result
    
    async def _verify_pull_requests(self, repo: str, expected: Dict) -> VerificationResult:
        """Verify pull requests migration"""
        result = VerificationResult("pull_requests")
        
        try:
            # Get PR counts
            all_prs_response = await self.github_client.get(
                f"/repos/{repo}/pulls",
                params={"state": "all", "per_page": 1}
            )
            
            if all_prs_response.status_code == 200:
                link_header = all_prs_response.headers.get("Link", "")
                page_count = self._extract_page_count_from_link_header(link_header)
                
                if page_count:
                    total_prs = page_count
                else:
                    # Single page - check if we have any PRs
                    prs = all_prs_response.json()
                    total_prs = len(prs)
                
                result.stats["total_prs"] = total_prs
                expected_count = expected.get("pr_count", 0)
                
                result.add_check("prs_migrated", True, {"count": total_prs})
                
                if expected_count > 0 and not self._is_within_tolerance(expected_count, total_prs, 0.05):
                    result.add_discrepancy(
                        f"PR count mismatch: expected {expected_count}, got {total_prs}",
                        "warning",
                        {"expected": expected_count, "actual": total_prs}
                    )
            
        except Exception as e:
            result.add_discrepancy(f"Pull requests verification failed: {str(e)}", "error")
        
        result.set_status()
        return result
    
    async def _verify_wiki(self, repo: str, expected: Dict) -> VerificationResult:
        """Verify wiki migration"""
        result = VerificationResult("wiki")
        
        try:
            # Check if wiki is enabled
            repo_response = await self.github_client.get(f"/repos/{repo}")
            if repo_response.status_code == 200:
                repo_data = repo_response.json()
                wiki_enabled = repo_data.get("has_wiki", False)
                
                result.stats["wiki_enabled"] = wiki_enabled
                result.add_check("wiki_enabled", wiki_enabled)
                
                if expected.get("wiki_enabled") and not wiki_enabled:
                    result.add_discrepancy("Wiki was expected but is not enabled", "warning")
            
        except Exception as e:
            result.add_discrepancy(f"Wiki verification failed: {str(e)}", "error")
        
        result.set_status()
        return result
    
    async def _verify_releases(self, repo: str, expected: Dict) -> VerificationResult:
        """Verify releases migration"""
        result = VerificationResult("releases")
        
        try:
            # Get releases
            releases_response = await self.github_client.get(f"/repos/{repo}/releases")
            if releases_response.status_code == 200:
                releases = releases_response.json()
                release_count = len(releases)
                expected_count = expected.get("release_count", 0)
                
                result.stats["release_count"] = release_count
                result.add_check("releases_migrated", True, {"count": release_count})
                
                if expected_count > 0 and release_count != expected_count:
                    result.add_discrepancy(
                        f"Release count mismatch: expected {expected_count}, got {release_count}",
                        "warning",
                        {"expected": expected_count, "actual": release_count}
                    )
                
                # Verify asset counts for sample releases
                total_assets = 0
                for release in releases[:5]:  # Sample first 5
                    assets = release.get("assets", [])
                    total_assets += len(assets)
                
                result.stats["total_assets"] = total_assets
                result.add_check("release_assets_exist", True, {"count": total_assets})
            
        except Exception as e:
            result.add_discrepancy(f"Releases verification failed: {str(e)}", "error")
        
        result.set_status()
        return result
    
    async def _verify_packages(self, repo: str, expected: Dict) -> VerificationResult:
        """Verify packages migration"""
        result = VerificationResult("packages")
        
        try:
            # Note: Package verification requires org-level API access
            expected_count = expected.get("package_count", 0)
            
            if expected_count == 0:
                result.stats["package_count"] = 0
                result.add_check("packages_not_expected", True, {
                    "note": "No packages expected for verification"
                })
            else:
                result.stats["package_count"] = 0
                result.add_discrepancy(
                    "Package verification not fully implemented - requires org-level API access",
                    "info",
                    {"expected": expected_count, "note": "Manual verification required"}
                )
            
        except Exception as e:
            result.add_discrepancy(f"Packages verification failed: {str(e)}", "error")
        
        result.set_status()
        return result
    
    async def _verify_settings(self, repo: str, expected: Dict) -> VerificationResult:
        """Verify repository settings"""
        result = VerificationResult("settings")
        
        try:
            # Verify branch protection rules
            branches_response = await self.github_client.get(f"/repos/{repo}/branches")
            if branches_response.status_code == 200:
                branches = branches_response.json()
                protected_count = sum(1 for b in branches if b.get("protected", False))
                
                result.stats["protected_branches"] = protected_count
                result.add_check("branch_protection_configured", True, {"count": protected_count})
            
            # Verify collaborators
            collaborators_response = await self.github_client.get(f"/repos/{repo}/collaborators")
            if collaborators_response.status_code == 200:
                collaborators = collaborators_response.json()
                collaborator_count = len(collaborators)
                
                result.stats["collaborator_count"] = collaborator_count
                result.add_check("collaborators_configured", True, {"count": collaborator_count})
            
            # Verify webhooks
            webhooks_response = await self.github_client.get(f"/repos/{repo}/hooks")
            if webhooks_response.status_code == 200:
                webhooks = webhooks_response.json()
                webhook_count = len(webhooks)
                
                result.stats["webhook_count"] = webhook_count
                result.add_check("webhooks_configured", True, {"count": webhook_count})
            
            # Verify repository settings
            repo_response = await self.github_client.get(f"/repos/{repo}")
            if repo_response.status_code == 200:
                repo_data = repo_response.json()
                result.stats["visibility"] = "private" if repo_data.get("private") else "public"
                result.stats["features"] = {
                    "issues": repo_data.get("has_issues", False),
                    "wiki": repo_data.get("has_wiki", False),
                    "projects": repo_data.get("has_projects", False),
                    "discussions": repo_data.get("has_discussions", False)
                }
                result.add_check("repository_settings_configured", True)
            
        except Exception as e:
            result.add_discrepancy(f"Settings verification failed: {str(e)}", "error")
        
        result.set_status()
        return result
    
    async def _verify_preservation(self, repo: str, expected: Dict) -> VerificationResult:
        """Verify preservation artifacts"""
        result = VerificationResult("preservation")
        
        try:
            # Check for .github/migration/ directory
            migration_response = await self.github_client.get(f"/repos/{repo}/contents/.github/migration")
            
            if migration_response.status_code == 200:
                migration_contents = migration_response.json()
                result.add_check("migration_directory_exists", True, {"file_count": len(migration_contents)})
                
                # Check for ID mappings file
                has_id_mappings = any(f.get("name") == "id_mappings.json" for f in migration_contents)
                result.add_check("id_mappings_exists", has_id_mappings)
                
                # Check for metadata
                has_metadata = any(f.get("name") == "migration_metadata.json" for f in migration_contents)
                result.add_check("migration_metadata_exists", has_metadata)
                
                result.stats["preservation_files"] = len(migration_contents)
            else:
                result.add_check("migration_directory_exists", False)
                if expected.get("preservation_expected", False):
                    result.add_discrepancy(
                        "Preservation artifacts expected but not found",
                        "warning"
                    )
            
        except Exception as e:
            result.add_discrepancy(f"Preservation verification failed: {str(e)}", "error")
        
        result.set_status()
        return result
    
    def _generate_verify_report(self, results: Dict[str, Dict], discrepancies: List[Dict]) -> Dict[str, Any]:
        """Generate comprehensive verification report"""
        return {
            "verification_timestamp": datetime.utcnow().isoformat(),
            "overall_status": self._calculate_overall_status(results),
            "components": results,
            "summary": {
                "total_components": len(results),
                "components_passed": sum(1 for r in results.values() if r["status"] == "success"),
                "components_with_warnings": sum(1 for r in results.values() if r["status"] == "warning"),
                "components_failed": sum(1 for r in results.values() if r["status"] == "error"),
                "total_checks": sum(len(r["checks"]) for r in results.values()),
                "total_discrepancies": len(discrepancies),
                "total_errors": sum(len(r["errors"]) for r in results.values()),
                "total_warnings": sum(len(r["warnings"]) for r in results.values())
            },
            "discrepancies": discrepancies
        }
    
    def _generate_verify_summary(self, results: Dict[str, Dict], discrepancies: List[Dict]) -> str:
        """Generate human-readable verification summary"""
        lines = [
            "# Migration Verification Summary",
            "",
            f"**Verification Date**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"**Overall Status**: {self._calculate_overall_status(results)}",
            "",
            "## Component Status",
            ""
        ]
        
        for component, data in results.items():
            status_emoji = {
                "success": "✅",
                "warning": "⚠️",
                "error": "❌",
                "pending": "⏳"
            }.get(data["status"], "❓")
            
            lines.append(f"### {status_emoji} {component.replace('_', ' ').title()}")
            lines.append(f"- **Status**: {data['status']}")
            lines.append(f"- **Checks**: {len(data['checks'])} performed")
            
            if data.get("stats"):
                lines.append("- **Statistics**:")
                for key, value in data["stats"].items():
                    lines.append(f"  - {key}: {value}")
            
            if data.get("errors"):
                lines.append(f"- **Errors**: {len(data['errors'])}")
                for error in data["errors"][:3]:  # Show first 3
                    lines.append(f"  - {error['message']}")
            
            if data.get("warnings"):
                lines.append(f"- **Warnings**: {len(data['warnings'])}")
                for warning in data["warnings"][:3]:  # Show first 3
                    lines.append(f"  - {warning['message']}")
            
            lines.append("")
        
        lines.extend([
            "## Summary",
            "",
            f"- **Total Components**: {len(results)}",
            f"- **Passed**: {sum(1 for r in results.values() if r['status'] == 'success')}",
            f"- **Warnings**: {sum(1 for r in results.values() if r['status'] == 'warning')}",
            f"- **Failed**: {sum(1 for r in results.values() if r['status'] == 'error')}",
            f"- **Total Discrepancies**: {len(discrepancies)}",
            ""
        ])
        
        if discrepancies:
            lines.extend([
                "## Critical Discrepancies",
                ""
            ])
            errors = [d for d in discrepancies if d.get("severity") == "error"]
            for error in errors[:10]:  # Show first 10 errors
                lines.append(f"- ❌ {error['message']}")
        
        return "\n".join(lines)
    
    def _generate_component_status(self, results: Dict[str, Dict]) -> Dict[str, Any]:
        """Generate component status summary"""
        return {
            component: {
                "status": data["status"],
                "checks_passed": sum(1 for c in data["checks"] if c["passed"]),
                "checks_total": len(data["checks"]),
                "errors": len(data["errors"]),
                "warnings": len(data["warnings"]),
                "stats": data.get("stats", {})
            }
            for component, data in results.items()
        }
    
    def _generate_discrepancies_report(self, discrepancies: List[Dict]) -> Dict[str, Any]:
        """Generate detailed discrepancies report"""
        return {
            "total": len(discrepancies),
            "by_severity": {
                "error": len([d for d in discrepancies if d.get("severity") == "error"]),
                "warning": len([d for d in discrepancies if d.get("severity") == "warning"]),
                "info": len([d for d in discrepancies if d.get("severity") == "info"])
            },
            "discrepancies": discrepancies
        }
    
    def _calculate_overall_status(self, results: Dict[str, Dict]) -> str:
        """Calculate overall verification status"""
        statuses = [r["status"] for r in results.values()]
        
        if "error" in statuses:
            return "FAILED"
        elif "warning" in statuses:
            return "PARTIAL"
        elif all(s == "success" for s in statuses):
            return "SUCCESS"
        else:
            return "PENDING"
    
    def generate_artifacts(self, data: Dict[str, Any]) -> Dict[str, str]:
        """Generate verification artifacts"""
        return {
            "verify_report": "verify/verify_report.json",
            "verify_summary": "verify/verify_summary.md",
            "component_status": "verify/component_status.json",
            "discrepancies": "verify/discrepancies.json"
        }
