"""Transform Agent - Convert GitLab to GitHub format using Microsoft Agent Framework"""

import json
import yaml
from typing import Any, Dict, List, Optional
from pathlib import Path
from app.agents.base_agent import BaseAgent, AgentResult
from app.utils.logging import get_logger
from app.utils.transformers import (
    CICDTransformer,
    UserMapper,
    ContentTransformer,
    GapAnalyzer,
    ProtectionRulesTransformer
)

logger = get_logger(__name__)


class TransformAgent(BaseAgent):
    """
    Transform Agent for converting GitLab constructs to GitHub equivalents.
    
    Using Microsoft Agent Framework patterns:
    - Intelligent transformation with LLM assistance (future)
    - Deterministic conversion rules
    - Gap analysis and reporting
    - Context-aware mappings
    
    Responsibilities:
    1. Convert GitLab CI to GitHub Actions workflows
    2. Map GitLab users to GitHub users
    3. Transform issues and merge requests
    4. Map labels, milestones, and other metadata
    5. Generate comprehensive gap analysis
    6. Create transformation artifacts for Apply Agent
    """
    
    def __init__(self):
        super().__init__(
            agent_name="TransformAgent",
            instructions="""
            You are specialized in transforming GitLab structures to GitHub equivalents.
            Your responsibilities:
            1. Convert .gitlab-ci.yml to GitHub Actions workflows
            2. Map GitLab CI variables to GitHub secrets/variables
            3. Transform branch protection rules
            4. Map user identities (GitLab → GitHub)
            5. Transform labels and milestones
            6. Generate conversion gap reports
            7. Create apply action plans
            
            Be deterministic and document all transformations.
            Identify and report features that cannot be directly mapped.
            """
        )
        
        # Initialize transformers
        self.cicd_transformer = CICDTransformer()
        self.user_mapper = UserMapper()
        self.content_transformer = ContentTransformer()
        self.gap_analyzer = GapAnalyzer()
        self.protection_transformer = ProtectionRulesTransformer()
    
    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        """Validate transform inputs"""
        required = ["run_id", "export_data", "output_dir"]
        return all(field in inputs for field in required)
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute transformation of exported GitLab data.
        
        Args:
            inputs: Dict with:
                - run_id: Migration run ID
                - export_data: Exported GitLab data
                - output_dir: Directory for transformation artifacts
                - gitlab_project: GitLab project path (optional)
                - github_repo: GitHub owner/repo (optional)
                - github_org_members: GitHub org members for user mapping (optional)
        
        Returns:
            AgentResult with transformation outputs and artifacts
        """
        self.log_event("INFO", f"Starting transformation for run {inputs['run_id']}")
        
        try:
            output_dir = Path(inputs["output_dir"])
            output_dir.mkdir(parents=True, exist_ok=True)
            
            export_data = inputs["export_data"]
            gitlab_project = inputs.get("gitlab_project", "")
            github_repo = inputs.get("github_repo", "")
            
            artifacts = []
            all_warnings = []
            all_errors = []
            
            # 1. Transform CI/CD workflows
            workflows_result = await self._transform_cicd(
                export_data.get("gitlab_ci_yaml"),
                output_dir
            )
            if workflows_result and workflows_result.get("artifacts"):
                artifacts.extend(workflows_result["artifacts"])
            if workflows_result and workflows_result.get("warnings"):
                all_warnings.extend(workflows_result["warnings"])
            if workflows_result and not workflows_result.get("success", True):
                if workflows_result.get("errors"):
                    all_errors.extend(workflows_result["errors"])
            
            # 2. Map users
            user_mappings_result = await self._map_users(
                export_data.get("users", []),
                inputs.get("github_org_members", []),
                output_dir
            )
            if user_mappings_result and user_mappings_result.get("artifacts"):
                artifacts.extend(user_mappings_result["artifacts"])
            if user_mappings_result and user_mappings_result.get("warnings"):
                all_warnings.extend(user_mappings_result["warnings"])
            if user_mappings_result and not user_mappings_result.get("success", True):
                if user_mappings_result.get("errors"):
                    all_errors.extend(user_mappings_result["errors"])
            
            # Set user mappings in content transformer
            if user_mappings_result and user_mappings_result.get("mappings"):
                self.content_transformer.set_user_mappings(user_mappings_result["mappings"])
            
            # 3. Transform issues
            issues_result = await self._transform_issues(
                export_data.get("issues", []),
                gitlab_project,
                github_repo,
                output_dir
            )
            if issues_result and issues_result.get("artifacts"):
                artifacts.extend(issues_result["artifacts"])
            if issues_result and issues_result.get("warnings"):
                all_warnings.extend(issues_result["warnings"])
            if issues_result and not issues_result.get("success", True):
                if issues_result.get("errors"):
                    all_errors.extend(issues_result["errors"])
            
            # 4. Transform merge requests
            mrs_result = await self._transform_merge_requests(
                export_data.get("merge_requests", []),
                gitlab_project,
                github_repo,
                output_dir
            )
            if mrs_result and mrs_result.get("artifacts"):
                artifacts.extend(mrs_result["artifacts"])
            if mrs_result and mrs_result.get("warnings"):
                all_warnings.extend(mrs_result["warnings"])
            if mrs_result and not mrs_result.get("success", True):
                if mrs_result.get("errors"):
                    all_errors.extend(mrs_result["errors"])
            
            # 5. Transform labels and milestones
            labels_result = await self._transform_labels(
                export_data.get("labels", []),
                output_dir
            )
            if labels_result and labels_result.get("artifacts"):
                artifacts.extend(labels_result["artifacts"])
            
            milestones_result = await self._transform_milestones(
                export_data.get("milestones", []),
                output_dir
            )
            if milestones_result and milestones_result.get("artifacts"):
                artifacts.extend(milestones_result["artifacts"])
            
            # 6. Transform branch protection rules
            protection_result = await self._transform_protection_rules(
                export_data.get("protected_branches", []),
                export_data.get("protected_tags", []),
                export_data.get("members", []),
                workflows_result.get("ci_jobs", []) if workflows_result else [],
                export_data.get("approval_rules", []),
                output_dir
            )
            if protection_result and protection_result.get("artifacts"):
                artifacts.extend(protection_result["artifacts"])
            if protection_result and protection_result.get("warnings"):
                all_warnings.extend(protection_result["warnings"])
            if protection_result and not protection_result.get("success", True):
                if protection_result.get("errors"):
                    all_errors.extend(protection_result["errors"])
            
            # 7. Perform gap analysis
            gap_analysis_result = await self._analyze_gaps(
                workflows_result,
                user_mappings_result,
                export_data.get("gitlab_features", []),
                output_dir
            )
            if gap_analysis_result and gap_analysis_result.get("artifacts"):
                artifacts.extend(gap_analysis_result["artifacts"])
            
            # Determine overall status
            status = "success" if not all_errors else "partial"
            
            self.log_event("INFO", f"Transformation completed with status: {status}")
            
            return AgentResult(
                status=status,
                outputs={
                    "run_id": inputs["run_id"],
                    "transform_complete": True,
                    "artifacts_generated": len(artifacts),
                    "workflows_count": len(workflows_result.get("workflows", [])) if workflows_result else 0,
                    "users_mapped": user_mappings_result.get("stats", {}).get("mapped", 0) if user_mappings_result else 0,
                    "issues_transformed": len(issues_result.get("issues", [])) if issues_result else 0,
                    "mrs_transformed": len(mrs_result.get("merge_requests", [])) if mrs_result else 0,
                    "branches_protected": protection_result.get("branches_protected", 0) if protection_result else 0,
                    "conversion_gaps": len(gap_analysis_result.get("gaps", [])) if gap_analysis_result else 0
                },
                artifacts=artifacts,
                errors=all_errors
            ).to_dict()
            
        except Exception as e:
            self.log_event("ERROR", f"Transform failed: {str(e)}")
            return AgentResult(
                status="failed",
                outputs={},
                artifacts=[],
                errors=[{"step": "transform", "message": str(e)}]
            ).to_dict()
    
    async def _transform_cicd(
        self,
        gitlab_ci_yaml: Optional[Any],
        output_dir: Path
    ) -> Optional[Dict[str, Any]]:
        """Transform GitLab CI to GitHub Actions workflows"""
        if not gitlab_ci_yaml:
            self.log_event("INFO", "No GitLab CI configuration found, skipping CI/CD transformation")
            return None
        
        self.log_event("INFO", "Transforming GitLab CI to GitHub Actions")
        
        result = self.cicd_transformer.transform({
            "gitlab_ci_yaml": gitlab_ci_yaml
        })
        
        if not result.success:
            self.log_event("ERROR", "CI/CD transformation failed")
            return {
                "success": False,
                "errors": result.errors,
                "warnings": result.warnings,
                "artifacts": []
            }
        
        # Save workflows
        workflows_dir = output_dir / "workflows"
        workflows_dir.mkdir(exist_ok=True)
        
        workflow_yaml = result.data.get("workflow_yaml", "")
        workflow_file = workflows_dir / "ci.yml"
        workflow_file.write_text(workflow_yaml)
        
        artifacts = [str(workflow_file)]
        
        # Extract CI job names for use in branch protection
        ci_jobs = []
        try:
            parsed_ci = gitlab_ci_yaml
            if isinstance(gitlab_ci_yaml, str):
                parsed_ci = yaml.safe_load(gitlab_ci_yaml)
            if isinstance(parsed_ci, dict):
                ci_jobs = self.protection_transformer.get_required_status_checks_from_ci(parsed_ci)
        except Exception as e:
            self.log_event("WARNING", f"Failed to extract CI jobs: {str(e)}")
        
        self.log_event("INFO", f"Generated GitHub Actions workflow: {workflow_file}")
        
        return {
            "success": True,
            "workflows": [str(workflow_file)],
            "ci_jobs": ci_jobs,
            "conversion_gaps": result.metadata.get("conversion_gaps", []),
            "artifacts": artifacts,
            "warnings": result.warnings,
            "errors": result.errors
        }
    
    async def _map_users(
        self,
        gitlab_users: List[Dict[str, Any]],
        github_org_members: List[Dict[str, Any]],
        output_dir: Path
    ) -> Optional[Dict[str, Any]]:
        """Map GitLab users to GitHub users"""
        if not gitlab_users:
            self.log_event("INFO", "No GitLab users found, skipping user mapping")
            return None
        
        self.log_event("INFO", f"Mapping {len(gitlab_users)} GitLab users to GitHub")
        
        result = self.user_mapper.transform({
            "gitlab_users": gitlab_users,
            "github_org_members": github_org_members
        })
        
        if not result.success:
            self.log_event("ERROR", "User mapping failed")
            return {
                "success": False,
                "errors": result.errors,
                "warnings": result.warnings,
                "artifacts": []
            }
        
        # Save user mappings
        mappings_file = output_dir / "user_mappings.json"
        with open(mappings_file, "w") as f:
            json.dump(result.data, f, indent=2)
        
        self.log_event("INFO", f"Generated user mappings: {mappings_file}")
        
        return {
            "success": True,
            "mappings": result.data.get("mappings", []),
            "stats": result.data.get("stats", {}),
            "unmapped_users": result.data.get("unmapped_users", []),
            "artifacts": [str(mappings_file)],
            "warnings": result.warnings,
            "errors": result.errors
        }
    
    async def _transform_issues(
        self,
        issues: List[Dict[str, Any]],
        gitlab_project: str,
        github_repo: str,
        output_dir: Path
    ) -> Optional[Dict[str, Any]]:
        """Transform GitLab issues to GitHub format"""
        if not issues:
            self.log_event("INFO", "No issues found, skipping issue transformation")
            return None
        
        self.log_event("INFO", f"Transforming {len(issues)} issues")
        
        transformed_issues = []
        errors = []
        
        for issue in issues:
            result = self.content_transformer.transform({
                "content_type": "issue",
                "content": issue,
                "gitlab_project": gitlab_project,
                "github_repo": github_repo
            })
            
            if result.success:
                transformed_issues.append(result.data)
            else:
                errors.extend(result.errors)
        
        # Save transformed issues
        issues_file = output_dir / "issues_transformed.json"
        with open(issues_file, "w") as f:
            json.dump(transformed_issues, f, indent=2)
        
        self.log_event("INFO", f"Transformed {len(transformed_issues)} issues: {issues_file}")
        
        return {
            "success": len(errors) == 0,
            "issues": transformed_issues,
            "artifacts": [str(issues_file)],
            "errors": errors,
            "warnings": []
        }
    
    async def _transform_merge_requests(
        self,
        merge_requests: List[Dict[str, Any]],
        gitlab_project: str,
        github_repo: str,
        output_dir: Path
    ) -> Optional[Dict[str, Any]]:
        """Transform GitLab merge requests to GitHub PRs"""
        if not merge_requests:
            self.log_event("INFO", "No merge requests found, skipping MR transformation")
            return None
        
        self.log_event("INFO", f"Transforming {len(merge_requests)} merge requests")
        
        transformed_mrs = []
        errors = []
        
        for mr in merge_requests:
            result = self.content_transformer.transform({
                "content_type": "merge_request",
                "content": mr,
                "gitlab_project": gitlab_project,
                "github_repo": github_repo
            })
            
            if result.success:
                transformed_mrs.append(result.data)
            else:
                errors.extend(result.errors)
        
        # Save transformed MRs
        mrs_file = output_dir / "pull_requests_transformed.json"
        with open(mrs_file, "w") as f:
            json.dump(transformed_mrs, f, indent=2)
        
        self.log_event("INFO", f"Transformed {len(transformed_mrs)} merge requests: {mrs_file}")
        
        return {
            "success": len(errors) == 0,
            "merge_requests": transformed_mrs,
            "artifacts": [str(mrs_file)],
            "errors": errors,
            "warnings": []
        }
    
    async def _transform_labels(
        self,
        labels: List[Any],
        output_dir: Path
    ) -> Optional[Dict[str, Any]]:
        """Transform and save labels"""
        if not labels:
            return None
        
        # Sanitize labels
        sanitized_labels = []
        for label in labels:
            if isinstance(label, dict):
                sanitized_labels.append({
                    "name": label.get("name", ""),
                    "color": label.get("color", "#000000"),
                    "description": label.get("description", "")
                })
            else:
                sanitized_labels.append({
                    "name": str(label),
                    "color": "#000000",
                    "description": ""
                })
        
        # Save labels
        labels_file = output_dir / "labels.json"
        with open(labels_file, "w") as f:
            json.dump(sanitized_labels, f, indent=2)
        
        self.log_event("INFO", f"Transformed {len(sanitized_labels)} labels: {labels_file}")
        
        return {
            "success": True,
            "labels": sanitized_labels,
            "artifacts": [str(labels_file)]
        }
    
    async def _transform_milestones(
        self,
        milestones: List[Dict[str, Any]],
        output_dir: Path
    ) -> Optional[Dict[str, Any]]:
        """Transform and save milestones"""
        if not milestones:
            return None
        
        # Transform milestones
        transformed_milestones = []
        for milestone in milestones:
            transformed_milestones.append({
                "title": milestone.get("title", ""),
                "description": milestone.get("description", ""),
                "due_on": milestone.get("due_date"),
                "state": "open" if milestone.get("state") == "active" else "closed"
            })
        
        # Save milestones
        milestones_file = output_dir / "milestones.json"
        with open(milestones_file, "w") as f:
            json.dump(transformed_milestones, f, indent=2)
        
        self.log_event("INFO", f"Transformed {len(transformed_milestones)} milestones: {milestones_file}")
        
        return {
            "success": True,
            "milestones": transformed_milestones,
            "artifacts": [str(milestones_file)]
        }
    
    async def _transform_protection_rules(
        self,
        protected_branches: List[Dict[str, Any]],
        protected_tags: List[Dict[str, Any]],
        members: List[Dict[str, Any]],
        ci_jobs: List[str],
        approval_rules: List[Dict[str, Any]],
        output_dir: Path
    ) -> Optional[Dict[str, Any]]:
        """Transform GitLab branch protection rules to GitHub protection settings"""
        if not protected_branches and not protected_tags:
            self.log_event("INFO", "No protected branches or tags found, skipping protection transformation")
            return None
        
        self.log_event("INFO", f"Transforming {len(protected_branches)} protected branches and {len(protected_tags)} protected tags")
        
        # Prepare input for transformer
        transform_input = {
            "protected_branches": protected_branches,
            "protected_tags": protected_tags,
            "project_members": members,
            "ci_jobs": ci_jobs,
            "approval_rules": approval_rules
        }
        
        result = self.protection_transformer.transform(transform_input)
        
        if not result.success:
            self.log_event("ERROR", "Protection rules transformation failed")
            return {
                "success": False,
                "errors": result.errors,
                "warnings": result.warnings,
                "artifacts": []
            }
        
        # Save protection rules
        protection_dir = output_dir / "protection"
        protection_dir.mkdir(exist_ok=True)
        
        artifacts = []
        
        # Save branch protection settings
        branch_protections = result.data.get("branch_protections", [])
        if branch_protections:
            protections_file = protection_dir / "branch_protections.json"
            with open(protections_file, "w") as f:
                json.dump(branch_protections, f, indent=2)
            artifacts.append(str(protections_file))
            self.log_event("INFO", f"Saved {len(branch_protections)} branch protection settings: {protections_file}")
        
        # Save tag protection settings
        tag_protections = result.data.get("protected_tags", [])
        if tag_protections:
            tags_file = protection_dir / "tag_protections.json"
            with open(tags_file, "w") as f:
                json.dump(tag_protections, f, indent=2)
            artifacts.append(str(tags_file))
            self.log_event("INFO", f"Saved {len(tag_protections)} tag protection settings: {tags_file}")
        
        # Save CODEOWNERS file if generated
        codeowners_content = result.data.get("codeowners_content")
        if codeowners_content:
            codeowners_file = protection_dir / "CODEOWNERS"
            with open(codeowners_file, "w") as f:
                f.write(codeowners_content)
            artifacts.append(str(codeowners_file))
            self.log_event("INFO", f"Generated CODEOWNERS file: {codeowners_file}")
        
        # Save conversion gaps
        gaps = result.data.get("gaps", [])
        if gaps:
            gaps_file = protection_dir / "protection_gaps.json"
            with open(gaps_file, "w") as f:
                json.dump(gaps, f, indent=2)
            artifacts.append(str(gaps_file))
            self.log_event("WARNING", f"Found {len(gaps)} protection conversion gaps: {gaps_file}")
        
        return {
            "success": True,
            "branches_protected": result.metadata.get("branches_protected", 0),
            "tags_protected": result.metadata.get("tags_protected", 0),
            "has_codeowners": result.metadata.get("has_codeowners", False),
            "conversion_gaps": gaps,
            "artifacts": artifacts,
            "warnings": result.warnings,
            "errors": result.errors
        }
    
    async def _analyze_gaps(
        self,
        workflows_result: Optional[Dict[str, Any]],
        user_mappings_result: Optional[Dict[str, Any]],
        gitlab_features: List[str],
        output_dir: Path
    ) -> Optional[Dict[str, Any]]:
        """Perform comprehensive gap analysis"""
        self.log_event("INFO", "Performing gap analysis")
        
        result = self.gap_analyzer.transform({
            "cicd_gaps": workflows_result.get("conversion_gaps", []) if workflows_result else [],
            "user_mappings": user_mappings_result if user_mappings_result else {},
            "gitlab_features": gitlab_features
        })
        
        if not result.success:
            self.log_event("ERROR", "Gap analysis failed")
            return {
                "success": False,
                "errors": result.errors,
                "artifacts": []
            }
        
        # Save gap analysis
        gaps_file = output_dir / "conversion_gaps.json"
        with open(gaps_file, "w") as f:
            json.dump(result.data, f, indent=2)
        
        # Generate gap report
        categorized_gaps = result.data.get("categorized_gaps", {})
        gap_report = self.gap_analyzer.generate_gap_report(categorized_gaps)
        
        report_file = output_dir / "conversion_gaps.md"
        report_file.write_text(gap_report)
        
        self.log_event("INFO", f"Generated gap analysis: {gaps_file}")
        
        return {
            "success": True,
            "gaps": result.data.get("gaps", []),
            "summary": result.data.get("summary", {}),
            "artifacts": [str(gaps_file), str(report_file)]
        }
    
    def generate_artifacts(self, data: Dict[str, Any]) -> Dict[str, str]:
        """Generate transformation artifacts"""
        return {
            "workflows": "transform/workflows/",
            "user_mappings": "transform/user_mappings.json",
            "issues_transformed": "transform/issues_transformed.json",
            "pull_requests_transformed": "transform/pull_requests_transformed.json",
            "labels": "transform/labels.json",
            "milestones": "transform/milestones.json",
            "conversion_gaps": "transform/conversion_gaps.json",
            "conversion_gaps_report": "transform/conversion_gaps.md"
        }
