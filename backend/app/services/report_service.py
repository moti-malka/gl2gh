"""Report service for generating migration summary reports"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from bson import ObjectId
from pathlib import Path
import json

from app.services.base_service import BaseService
from app.services.run_service import RunService
from app.services.artifact_service import ArtifactService


class MigrationReportGenerator(BaseService):
    """Service for generating comprehensive migration reports"""
    
    def __init__(self, db=None):
        super().__init__(db)
        self.run_service = RunService(db)
        self.artifact_service = ArtifactService(db)
    
    async def generate(self, run_id: str, format: str = "json") -> Dict[str, Any]:
        """
        Generate a comprehensive migration report
        
        Args:
            run_id: Run ID
            format: Output format (json, markdown, html)
            
        Returns:
            Report in the specified format
            
        Raises:
            ValueError: If run_id is not valid or format is invalid
            RuntimeError: If report generation fails
        """
        if format not in ["json", "markdown", "html"]:
            raise ValueError(f"Invalid format: {format}. Must be json, markdown, or html")
        
        # Get run details
        run = await self.run_service.get_run(run_id)
        if not run:
            raise ValueError(f"Run not found: {run_id}")
        
        # Gather report data
        report_data = await self._gather_report_data(run_id, run)
        
        # Format based on requested format
        if format == "json":
            return report_data
        elif format == "markdown":
            return {"content": self._format_as_markdown(report_data), "format": "markdown"}
        elif format == "html":
            return {"content": self._format_as_html(report_data), "format": "html"}
    
    async def _gather_report_data(self, run_id: str, run) -> Dict[str, Any]:
        """Gather all data needed for the report"""
        
        # Get project details
        from app.services.project_service import ProjectService
        project_service = ProjectService(self._db)
        project = await project_service.get_project(str(run.project_id))
        
        # Get run projects (individual GitLab projects in this run)
        run_projects = await self._get_run_projects(run_id)
        
        # Get artifacts
        artifacts = await self.artifact_service.list_artifacts(run_id)
        
        # Calculate summary statistics
        summary = await self._calculate_summary(run_id, run_projects, artifacts)
        
        # Identify manual actions
        manual_actions = await self._identify_manual_actions(run_id, run_projects, artifacts)
        
        # Get migration details
        migration_details = await self._get_migration_details(run_id, run_projects, artifacts)
        
        # Build report structure
        report = {
            "run_id": run_id,
            "project": {
                "name": project.name if project else "Unknown",
                "id": str(run.project_id)
            },
            "status": run.status,
            "mode": run.mode,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "duration_seconds": self._calculate_duration(run),
            "summary": summary,
            "manual_actions": manual_actions,
            "migration_details": migration_details,
            "error": run.error,
            "generated_at": datetime.utcnow().isoformat()
        }
        
        return report
    
    async def _get_run_projects(self, run_id: str) -> List[Dict[str, Any]]:
        """Get all run projects for this run"""
        if not ObjectId.is_valid(run_id):
            return []
        
        cursor = self.db["run_projects"].find({"run_id": ObjectId(run_id)})
        projects = []
        async for project in cursor:
            projects.append(project)
        return projects
    
    async def _calculate_summary(
        self, 
        run_id: str, 
        run_projects: List[Dict[str, Any]], 
        artifacts: List
    ) -> Dict[str, Any]:
        """Calculate summary statistics"""
        
        # Count projects by status
        total_projects = len(run_projects)
        completed_projects = sum(1 for p in run_projects if p.get("stage_status", {}).get("verify") == "COMPLETED")
        failed_projects = sum(1 for p in run_projects if len(p.get("errors", [])) > 0)
        
        # Aggregate component statistics from artifacts
        issues_stats = {"migrated": 0, "skipped": 0, "failed": 0}
        mrs_stats = {"migrated": 0, "skipped": 0, "failed": 0}
        pipelines_stats = {"migrated": 0, "skipped": 0, "failed": 0}
        releases_stats = {"migrated": 0, "skipped": 0, "failed": 0}
        
        # Parse apply_report artifacts to get detailed stats
        apply_reports = [a for a in artifacts if a.type == "apply_report"]
        for report_artifact in apply_reports:
            stats = await self._parse_apply_report(run_id, report_artifact)
            if stats:
                issues_stats["migrated"] += stats.get("issues", {}).get("migrated", 0)
                issues_stats["failed"] += stats.get("issues", {}).get("failed", 0)
                mrs_stats["migrated"] += stats.get("pull_requests", {}).get("migrated", 0)
                mrs_stats["failed"] += stats.get("pull_requests", {}).get("failed", 0)
                pipelines_stats["migrated"] += stats.get("workflows", {}).get("migrated", 0)
                pipelines_stats["failed"] += stats.get("workflows", {}).get("failed", 0)
                releases_stats["migrated"] += stats.get("releases", {}).get("migrated", 0)
                releases_stats["failed"] += stats.get("releases", {}).get("failed", 0)
        
        summary = {
            "projects": {
                "total": total_projects,
                "completed": completed_projects,
                "failed": failed_projects
            },
            "components": {
                "issues": issues_stats,
                "merge_requests_to_prs": mrs_stats,
                "pipelines_to_actions": pipelines_stats,
                "releases": releases_stats
            }
        }
        
        return summary
    
    async def _parse_apply_report(self, run_id: str, artifact) -> Optional[Dict[str, Any]]:
        """Parse an apply_report artifact to extract statistics"""
        try:
            # Get the run to find artifact_root
            run = await self.run_service.get_run(run_id)
            if not run or not run.artifact_root:
                return None
            
            report_path = Path(run.artifact_root) / artifact.path
            if not report_path.exists():
                return None
            
            with open(report_path, 'r') as f:
                report_data = json.load(f)
            
            # Extract statistics from the report
            stats = {}
            
            # Count issues
            issues = report_data.get("results", {}).get("issues", [])
            stats["issues"] = {
                "migrated": sum(1 for i in issues if i.get("success", False)),
                "failed": sum(1 for i in issues if not i.get("success", False))
            }
            
            # Count pull requests
            prs = report_data.get("results", {}).get("pull_requests", [])
            stats["pull_requests"] = {
                "migrated": sum(1 for pr in prs if pr.get("success", False)),
                "failed": sum(1 for pr in prs if not pr.get("success", False))
            }
            
            # Count workflows
            workflows = report_data.get("results", {}).get("workflows", [])
            stats["workflows"] = {
                "migrated": sum(1 for w in workflows if w.get("success", False)),
                "failed": sum(1 for w in workflows if not w.get("success", False))
            }
            
            # Count releases
            releases = report_data.get("results", {}).get("releases", [])
            stats["releases"] = {
                "migrated": sum(1 for r in releases if r.get("success", False)),
                "failed": sum(1 for r in releases if not r.get("success", False))
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error parsing apply report {artifact.path}: {e}")
            return None
    
    async def _identify_manual_actions(
        self, 
        run_id: str, 
        run_projects: List[Dict[str, Any]], 
        artifacts: List
    ) -> List[Dict[str, str]]:
        """Identify manual actions required after migration"""
        manual_actions = []
        
        # Check for CI/CD secrets that need manual copying
        # This is a common manual action mentioned in the requirements
        for project in run_projects:
            readiness = project.get("readiness", {})
            if readiness.get("has_ci_variables"):
                manual_actions.append({
                    "type": "ci_secrets",
                    "priority": "high",
                    "description": f"CI/CD secrets for {project.get('path_with_namespace')} need to be copied manually",
                    "project": project.get("path_with_namespace")
                })
        
        # Check for webhooks that need URL updates
        for project in run_projects:
            facts = project.get("facts", {})
            if facts.get("webhook_count", 0) > 0:
                manual_actions.append({
                    "type": "webhooks",
                    "priority": "medium",
                    "description": f"{facts['webhook_count']} webhooks for {project.get('path_with_namespace')} need URL updates",
                    "project": project.get("path_with_namespace")
                })
        
        # Check verification reports for discrepancies
        verify_reports = [a for a in artifacts if a.type == "verify_report"]
        for report_artifact in verify_reports:
            discrepancies = await self._parse_verify_report(run_id, report_artifact)
            if discrepancies:
                for disc in discrepancies:
                    manual_actions.append({
                        "type": "verification_issue",
                        "priority": "high",
                        "description": disc,
                        "project": report_artifact.metadata.get("path_with_namespace", "Unknown")
                    })
        
        return manual_actions
    
    async def _parse_verify_report(self, run_id: str, artifact) -> List[str]:
        """Parse verification report to find discrepancies"""
        try:
            run = await self.run_service.get_run(run_id)
            if not run or not run.artifact_root:
                return []
            
            report_path = Path(run.artifact_root) / artifact.path
            if not report_path.exists():
                return []
            
            with open(report_path, 'r') as f:
                report_data = json.load(f)
            
            discrepancies = []
            for disc in report_data.get("discrepancies", []):
                discrepancies.append(disc.get("description", "Unknown verification issue"))
            
            return discrepancies
            
        except Exception as e:
            self.logger.error(f"Error parsing verify report {artifact.path}: {e}")
            return []
    
    async def _get_migration_details(
        self, 
        run_id: str, 
        run_projects: List[Dict[str, Any]], 
        artifacts: List
    ) -> Dict[str, Any]:
        """Get detailed migration information"""
        
        details = {
            "projects": [],
            "artifacts": []
        }
        
        # Add project details
        for project in run_projects:
            project_detail = {
                "gitlab_project_id": project.get("gitlab_project_id"),
                "path": project.get("path_with_namespace"),
                "status": project.get("stage_status", {}),
                "errors": project.get("errors", [])
            }
            details["projects"].append(project_detail)
        
        # Add artifact summary
        artifact_types = {}
        for artifact in artifacts:
            artifact_type = artifact.type
            if artifact_type not in artifact_types:
                artifact_types[artifact_type] = 0
            artifact_types[artifact_type] += 1
        
        details["artifacts"] = [
            {"type": atype, "count": count}
            for atype, count in artifact_types.items()
        ]
        
        return details
    
    def _calculate_duration(self, run) -> Optional[float]:
        """Calculate run duration in seconds"""
        if run.started_at and run.finished_at:
            delta = run.finished_at - run.started_at
            return delta.total_seconds()
        return None
    
    def _format_as_markdown(self, report_data: Dict[str, Any]) -> str:
        """Format report as Markdown"""
        
        md = []
        md.append("# Migration Report\n")
        
        # Header with status
        status_emoji = "✅" if report_data["status"] == "COMPLETED" else "❌" if report_data["status"] == "FAILED" else "⏳"
        md.append(f"**Project:** {report_data['project']['name']}")
        md.append(f"**Status:** {status_emoji} {report_data['status']}\n")
        
        # Duration
        if report_data.get("duration_seconds"):
            duration_mins = report_data["duration_seconds"] / 60
            md.append(f"**Duration:** {duration_mins:.1f} minutes\n")
        
        # Summary table
        md.append("## Summary\n")
        md.append("| Component | Migrated | Skipped | Failed |")
        md.append("|-----------|----------|---------|--------|")
        
        components = report_data["summary"]["components"]
        md.append(f"| Issues | {components['issues']['migrated']} | {components['issues']['skipped']} | {components['issues']['failed']} |")
        md.append(f"| Merge Requests → PRs | {components['merge_requests_to_prs']['migrated']} | {components['merge_requests_to_prs']['skipped']} | {components['merge_requests_to_prs']['failed']} |")
        md.append(f"| CI/CD Pipelines → Actions | {components['pipelines_to_actions']['migrated']} | {components['pipelines_to_actions']['skipped']} | {components['pipelines_to_actions']['failed']} |")
        md.append(f"| Releases | {components['releases']['migrated']} | {components['releases']['skipped']} | {components['releases']['failed']} |\n")
        
        # Manual actions
        if report_data["manual_actions"]:
            md.append("## Manual Actions Required ⚠️\n")
            
            # Group by type
            actions_by_type = {}
            for action in report_data["manual_actions"]:
                atype = action["type"]
                if atype not in actions_by_type:
                    actions_by_type[atype] = []
                actions_by_type[atype].append(action)
            
            for idx, (atype, actions) in enumerate(actions_by_type.items(), 1):
                if atype == "ci_secrets":
                    md.append(f"{idx}. **{len(actions)} CI/CD Secrets** need to be copied manually")
                elif atype == "webhooks":
                    md.append(f"{idx}. **{len(actions)} Webhooks** need URL updates")
                elif atype == "verification_issue":
                    md.append(f"{idx}. **{len(actions)} Verification Issues** need attention")
                else:
                    md.append(f"{idx}. **{len(actions)} {atype}** items need attention")
            md.append("")
        
        # Project details
        md.append("## Projects\n")
        projects = report_data["migration_details"]["projects"]
        md.append(f"**Total Projects:** {len(projects)}\n")
        
        for project in projects:
            status = project["status"]
            verify_status = status.get("verify", "PENDING")
            status_emoji = "✅" if verify_status == "COMPLETED" else "❌" if verify_status == "FAILED" else "⏳"
            md.append(f"- {status_emoji} `{project['path']}`")
            if project.get("errors"):
                md.append(f"  - **Errors:** {len(project['errors'])}")
        
        md.append(f"\n---\n")
        md.append(f"*Report generated at {report_data['generated_at']}*")
        
        return "\n".join(md)
    
    def _format_as_html(self, report_data: Dict[str, Any]) -> str:
        """Format report as HTML"""
        import html as html_module
        
        # Status emoji
        status_emoji = "✅" if report_data["status"] == "COMPLETED" else "❌" if report_data["status"] == "FAILED" else "⏳"
        
        # Escape user-provided strings to prevent HTML injection
        project_name = html_module.escape(report_data['project']['name'])
        status = html_module.escape(report_data['status'])
        
        html = []
        html.append("<!DOCTYPE html>")
        html.append("<html>")
        html.append("<head>")
        html.append("<title>Migration Report</title>")
        html.append("<style>")
        html.append("body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }")
        html.append("h1 { color: #333; }")
        html.append("h2 { color: #555; border-bottom: 2px solid #ddd; padding-bottom: 10px; }")
        html.append("table { border-collapse: collapse; width: 100%; margin: 20px 0; }")
        html.append("th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }")
        html.append("th { background-color: #f5f5f5; font-weight: bold; }")
        html.append("tr:nth-child(even) { background-color: #f9f9f9; }")
        html.append(".status { font-size: 1.2em; margin: 10px 0; }")
        html.append(".manual-actions { background-color: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0; }")
        html.append(".project-list { list-style: none; padding: 0; }")
        html.append(".project-list li { padding: 8px; margin: 5px 0; background-color: #f8f9fa; }")
        html.append(".footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; }")
        html.append("</style>")
        html.append("</head>")
        html.append("<body>")
        
        # Header
        html.append("<h1>Migration Report</h1>")
        html.append(f"<p><strong>Project:</strong> {project_name}</p>")
        html.append(f"<p class='status'><strong>Status:</strong> {status_emoji} {status}</p>")
        
        if report_data.get("duration_seconds"):
            duration_mins = report_data["duration_seconds"] / 60
            html.append(f"<p><strong>Duration:</strong> {duration_mins:.1f} minutes</p>")
        
        # Summary table
        html.append("<h2>Summary</h2>")
        html.append("<table>")
        html.append("<thead>")
        html.append("<tr><th>Component</th><th>Migrated</th><th>Skipped</th><th>Failed</th></tr>")
        html.append("</thead>")
        html.append("<tbody>")
        
        components = report_data["summary"]["components"]
        html.append(f"<tr><td>Issues</td><td>{components['issues']['migrated']}</td><td>{components['issues']['skipped']}</td><td>{components['issues']['failed']}</td></tr>")
        html.append(f"<tr><td>Merge Requests → PRs</td><td>{components['merge_requests_to_prs']['migrated']}</td><td>{components['merge_requests_to_prs']['skipped']}</td><td>{components['merge_requests_to_prs']['failed']}</td></tr>")
        html.append(f"<tr><td>CI/CD Pipelines → Actions</td><td>{components['pipelines_to_actions']['migrated']}</td><td>{components['pipelines_to_actions']['skipped']}</td><td>{components['pipelines_to_actions']['failed']}</td></tr>")
        html.append(f"<tr><td>Releases</td><td>{components['releases']['migrated']}</td><td>{components['releases']['skipped']}</td><td>{components['releases']['failed']}</td></tr>")
        
        html.append("</tbody>")
        html.append("</table>")
        
        # Manual actions
        if report_data["manual_actions"]:
            html.append("<h2>Manual Actions Required ⚠️</h2>")
            html.append("<div class='manual-actions'>")
            html.append("<ol>")
            
            # Group by type
            actions_by_type = {}
            for action in report_data["manual_actions"]:
                atype = action["type"]
                if atype not in actions_by_type:
                    actions_by_type[atype] = []
                actions_by_type[atype].append(action)
            
            for atype, actions in actions_by_type.items():
                # Escape action type to prevent HTML injection
                escaped_type = html_module.escape(atype)
                if atype == "ci_secrets":
                    html.append(f"<li><strong>{len(actions)} CI/CD Secrets</strong> need to be copied manually</li>")
                elif atype == "webhooks":
                    html.append(f"<li><strong>{len(actions)} Webhooks</strong> need URL updates</li>")
                elif atype == "verification_issue":
                    html.append(f"<li><strong>{len(actions)} Verification Issues</strong> need attention</li>")
                else:
                    html.append(f"<li><strong>{len(actions)} {escaped_type}</strong> items need attention</li>")
            
            html.append("</ol>")
            html.append("</div>")
        
        # Project details
        html.append("<h2>Projects</h2>")
        projects = report_data["migration_details"]["projects"]
        html.append(f"<p><strong>Total Projects:</strong> {len(projects)}</p>")
        html.append("<ul class='project-list'>")
        
        for project in projects:
            status = project["status"]
            verify_status = status.get("verify", "PENDING")
            status_emoji = "✅" if verify_status == "COMPLETED" else "❌" if verify_status == "FAILED" else "⏳"
            # Escape project path to prevent HTML injection
            escaped_path = html_module.escape(project['path'])
            html.append(f"<li>{status_emoji} <code>{escaped_path}</code>")
            if project.get("errors"):
                html.append(f" - <strong>Errors:</strong> {len(project['errors'])}")
            html.append("</li>")
        
        html.append("</ul>")
        
        # Footer
        html.append(f"<div class='footer'>")
        html.append(f"<p><em>Report generated at {report_data['generated_at']}</em></p>")
        html.append("</div>")
        
        html.append("</body>")
        html.append("</html>")
        
        return "\n".join(html)
