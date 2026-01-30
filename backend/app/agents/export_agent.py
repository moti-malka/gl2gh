"""Export Agent - Export GitLab project data using Microsoft Agent Framework"""

import json
import subprocess
import shutil
import urllib.parse
import asyncio
import re
from typing import Any, Dict, List, Optional, Set
from pathlib import Path
from datetime import datetime
from app.agents.base_agent import BaseAgent, AgentResult
from app.agents.export_checkpoint import ExportCheckpoint
from app.clients.gitlab_client import GitLabClient
from app.utils.logging import get_logger

logger = get_logger(__name__)


# Attachment URL patterns for GitLab
ATTACHMENT_PATTERNS = [
    r'!\[.*?\]\((/uploads/[^)]+)\)',           # Images: ![alt](/uploads/...)
    r'\[.*?\]\((/uploads/[^)]+)\)',            # Files: [name](/uploads/...)
    r'(/uploads/[a-fA-F0-9]+/[^\s)]+)',        # Direct upload links (case-insensitive hex)
]

# Maximum file size for GitHub (100 MB limit, warn at 50 MB)
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
WARN_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


class ExportAgent(BaseAgent):
    """
    Export Agent for extracting GitLab project data.
    
    Using Microsoft Agent Framework patterns:
    - Tool integration (GitLab API, git commands)
    - Deterministic export operations
    - Artifact generation and storage
    - Error handling with partial success support
    
    Exports all components:
    - Repository (git bundle, LFS, submodules)
    - CI/CD (gitlab-ci.yml, variables, environments, schedules)
    - Issues (with comments, attachments)
    - Merge Requests (with discussions, approvals)
    - Wiki (git bundle)
    - Releases (with assets)
    - Packages (metadata)
    - Settings (protections, members, webhooks)
    """
    
    def __init__(self):
        super().__init__(
            agent_name="ExportAgent",
            instructions="""
            You are specialized in exporting GitLab project data for migration.
            Your responsibilities:
            1. Export git repository as bundle
            2. Export Git LFS objects (if present)
            3. Export .gitlab-ci.yml and included files
            4. Export issues with comments and attachments
            5. Export merge requests with discussions
            6. Export wiki content
            7. Export releases and assets
            8. Export project settings and metadata
            
            Handle API errors gracefully and export partial data when possible.
            Generate comprehensive export manifest for tracking.
            """
        )
        self.gitlab_client: Optional[GitLabClient] = None
        self.checkpoint: Optional[ExportCheckpoint] = None
        self.export_stats = {
            "repository": {"status": "pending"},
            "ci": {"status": "pending"},
            "issues": {"status": "pending", "count": 0},
            "merge_requests": {"status": "pending", "count": 0},
            "wiki": {"status": "pending"},
            "releases": {"status": "pending", "count": 0},
            "packages": {"status": "pending", "count": 0},
            "settings": {"status": "pending"}
        }
    
    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        """Validate export inputs"""
        required = ["gitlab_url", "gitlab_token", "project_id", "output_dir"]
        if not all(field in inputs for field in required):
            self.log_event("ERROR", f"Missing required inputs: {required}")
            return False
        
        # Validate project_id is integer
        try:
            int(inputs["project_id"])
        except (ValueError, TypeError):
            self.log_event("ERROR", f"Invalid project_id: {inputs['project_id']}")
            return False
        
        return True
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute export process"""
        project_id = int(inputs['project_id'])
        output_dir = Path(inputs["output_dir"])
        resume = inputs.get("resume", False)
        
        self.log_event("INFO", f"Starting export for project {project_id} (resume={resume})")
        
        # Initialize checkpoint
        checkpoint_file = output_dir / ".export_checkpoint.json"
        self.checkpoint = ExportCheckpoint(checkpoint_file)
        
        if resume:
            progress = self.checkpoint.get_progress_summary()
            self.log_event("INFO", f"Resuming export: {progress['completed']}/{progress['total_components']} components completed")
        
        # Initialize GitLab client
        self.gitlab_client = GitLabClient(
            base_url=inputs["gitlab_url"],
            token=inputs["gitlab_token"],
            max_requests_per_minute=inputs.get("max_requests_per_minute", 300)
        )
        
        errors = []
        artifacts = []
        
        try:
            # Create output directory structure
            output_dir.mkdir(parents=True, exist_ok=True)
            self._create_directory_structure(output_dir)
            
            # Get project details first
            self.log_event("INFO", "Fetching project details")
            project = await self.gitlab_client.get_project(project_id)
            project_path = project.get('path_with_namespace', str(project_id))
            
            # Store project info in checkpoint
            self.checkpoint.set_metadata("project_id", project_id)
            self.checkpoint.set_metadata("project_path", project_path)
            
            # Export components in sequence
            components = [
                ("repository", self._export_repository),
                ("ci", self._export_ci_cd),
                ("issues", self._export_issues),
                ("merge_requests", self._export_merge_requests),
                ("wiki", self._export_wiki),
                ("releases", self._export_releases),
                ("packages", self._export_packages),
                ("settings", self._export_settings)
            ]
            
            for component_name, export_func in components:
                # Skip if already completed and resume is enabled
                if resume and self.checkpoint.is_component_completed(component_name):
                    self.log_event("INFO", f"Skipping {component_name} (already completed)")
                    self.export_stats[component_name]["status"] = "completed"
                    continue
                
                try:
                    self.log_event("INFO", f"Exporting {component_name}...")
                    self.checkpoint.mark_component_started(component_name)
                    
                    result = await export_func(project_id, project, output_dir)
                    
                    if result.get("success"):
                        self.export_stats[component_name]["status"] = "completed"
                        if "count" in result:
                            self.export_stats[component_name]["count"] = result["count"]
                        if "artifacts" in result:
                            artifacts.extend(result["artifacts"])
                        
                        self.checkpoint.mark_component_completed(component_name, success=True)
                    else:
                        self.export_stats[component_name]["status"] = "partial"
                        if "error" in result:
                            errors.append({
                                "component": component_name,
                                "message": result["error"]
                            })
                        
                        self.checkpoint.mark_component_completed(
                            component_name,
                            success=False,
                            error=result.get("error")
                        )
                    
                except Exception as e:
                    self.log_event("ERROR", f"Failed to export {component_name}: {e}")
                    self.export_stats[component_name]["status"] = "failed"
                    error_msg = str(e)
                    errors.append({
                        "component": component_name,
                        "message": error_msg
                    })
                    
                    self.checkpoint.mark_component_completed(
                        component_name,
                        success=False,
                        error=error_msg
                    )
            
            # Generate export manifest
            manifest_path = output_dir / "export_manifest.json"
            manifest = {
                "project_id": project_id,
                "project_path": project_path,
                "exported_at": datetime.utcnow().isoformat(),
                "gitlab_url": inputs["gitlab_url"],
                "components": self.export_stats,
                "checkpoint_summary": self.checkpoint.get_progress_summary(),
                "errors": errors
            }
            
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            
            artifacts.append(str(manifest_path.relative_to(output_dir.parent)))
            
            # Determine overall status
            completed = sum(1 for c in self.export_stats.values() if c["status"] == "completed")
            failed = sum(1 for c in self.export_stats.values() if c["status"] == "failed")
            
            if failed == 0:
                status = "success"
            elif completed > 0:
                status = "partial"
            else:
                status = "failed"
            
            self.log_event("INFO", f"Export completed with status: {status}")
            
            return AgentResult(
                status=status,
                outputs={
                    "project_id": project_id,
                    "project_path": project_path,
                    "export_stats": self.export_stats,
                    "checkpoint_summary": self.checkpoint.get_progress_summary(),
                    "output_dir": str(output_dir)
                },
                artifacts=artifacts,
                errors=errors
            ).to_dict()
            
        except Exception as e:
            self.log_event("ERROR", f"Export failed: {str(e)}")
            return AgentResult(
                status="failed",
                outputs={},
                artifacts=artifacts,
                errors=[{"step": "export", "message": str(e)}]
            ).to_dict()
        
        finally:
            # Close GitLab client
            if self.gitlab_client:
                await self.gitlab_client.close()
    
    def _sanitize_error_message(self, error_msg: str, token: str) -> str:
        """Remove sensitive information from error messages"""
        # Replace token with placeholder
        if token and token in error_msg:
            error_msg = error_msg.replace(token, "***TOKEN***")
        # Replace common auth patterns
        error_msg = error_msg.replace("oauth2:", "***AUTH***:")
        return error_msg
    
    def _extract_attachments(self, content: str) -> Set[str]:
        """
        Extract attachment URLs from content.
        
        Args:
            content: Markdown content to scan
            
        Returns:
            Set of attachment paths found
        """
        if not content:
            return set()
        
        attachments = set()
        for pattern in ATTACHMENT_PATTERNS:
            matches = re.findall(pattern, content)
            attachments.update(matches)
        
        return attachments
    
    async def _download_attachment(
        self,
        project_path: str,
        attachment_path: str,
        output_dir: Path
    ) -> Optional[Path]:
        """
        Download an attachment from GitLab.
        
        Args:
            project_path: GitLab project path (e.g., "group/project")
            attachment_path: Attachment path (e.g., "/uploads/abc123/file.png")
            output_dir: Base output directory for attachments
            
        Returns:
            Local path to downloaded file, or None if failed
        """
        try:
            # Validate attachment path to prevent path traversal
            if ".." in attachment_path or attachment_path.startswith("/.."):
                self.log_event("WARNING", f"Suspicious attachment path detected: {attachment_path}")
                return None
            
            # Construct full URL
            # GitLab attachment URLs are: {base_url}/{project_path}{attachment_path}
            url = f"{self.gitlab_client.base_url}/{project_path}{attachment_path}"
            
            # Create filename from path (keep hash for uniqueness)
            # /uploads/abc123def/screenshot.png -> abc123def_screenshot.png
            path_parts = attachment_path.strip('/').split('/')
            if len(path_parts) >= 3:  # uploads/hash/filename
                hash_part = path_parts[1]
                filename = path_parts[-1]
                
                # Sanitize filename to prevent issues with special characters
                import re
                # Allow only alphanumeric, underscore, hyphen, and single period for extension
                safe_filename_part = re.sub(r'[^\w\-.]', '_', filename)
                # Prevent multiple dots (except for extension)
                parts = safe_filename_part.rsplit('.', 1)
                if len(parts) == 2:
                    name_part = parts[0].replace('.', '_')
                    ext_part = parts[1]
                    safe_filename_part = f"{name_part}.{ext_part}"
                
                safe_filename = f"{hash_part}_{safe_filename_part}"
            else:
                # Fallback: use sanitized full path
                safe_filename = re.sub(r'[^\w\-.]', '_', attachment_path.replace('/', '_').strip('_'))
            
            output_path = output_dir / safe_filename
            
            # Download the file
            success = await self.gitlab_client.download_file(url, output_path)
            
            if success:
                # Check file size after download
                file_size = output_path.stat().st_size
                if file_size > MAX_FILE_SIZE:
                    self.log_event("WARNING", f"Attachment {attachment_path} exceeds GitHub limit ({file_size / 1024 / 1024:.1f} MB > 100 MB)")
                    output_path.unlink()  # Delete oversized file
                    return None
                elif file_size > WARN_FILE_SIZE:
                    self.log_event("WARNING", f"Large attachment {attachment_path}: {file_size / 1024 / 1024:.1f} MB (GitHub limit is 100 MB)")
                
                self.log_event("DEBUG", f"Downloaded attachment: {attachment_path} -> {safe_filename}")
                return output_path
            else:
                self.log_event("WARNING", f"Failed to download attachment: {attachment_path}")
                return None
                
        except Exception as e:
            self.log_event("WARNING", f"Error downloading attachment {attachment_path}: {e}")
            return None
    
    def _create_directory_structure(self, output_dir: Path):
        """Create export directory structure"""
        subdirs = [
            "repository",
            "repository/lfs",
            "ci",
            "ci/includes",
            "issues",
            "issues/attachments",
            "merge_requests",
            "merge_requests/attachments",
            "wiki",
            "releases",
            "releases/assets",
            "packages",
            "settings"
        ]
        
        for subdir in subdirs:
            (output_dir / subdir).mkdir(parents=True, exist_ok=True)
    
    async def _export_repository(
        self,
        project_id: int,
        project: Dict[str, Any],
        output_dir: Path
    ) -> Dict[str, Any]:
        """Export repository as git bundle"""
        try:
            repo_dir = output_dir / "repository"
            bundle_path = repo_dir / "bundle.git"
            
            # Get repository clone URL
            http_url = project.get('http_url_to_repo')
            if not http_url:
                return {"success": False, "error": "No repository URL found"}
            
            # Add authentication to URL
            auth_url = http_url.replace('://', f'://oauth2:{self.gitlab_client.token}@')
            
            self.log_event("INFO", f"Creating git bundle from {http_url}")
            
            # Create temporary clone directory
            temp_dir = repo_dir / "temp_clone"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # Get timeout from config or use defaults
            clone_timeout = 600  # 10 minutes for large repos
            bundle_timeout = 300  # 5 minutes for bundle creation
            
            try:
                # Clone repository (bare)
                result = subprocess.run(
                    ['git', 'clone', '--mirror', auth_url, str(temp_dir)],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=clone_timeout
                )
                
                # Create bundle
                result = subprocess.run(
                    ['git', 'bundle', 'create', str(bundle_path), '--all'],
                    cwd=temp_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=bundle_timeout
                )
                
                # Export submodule info if present
                try:
                    result = subprocess.run(
                        ['git', 'config', '--file', '.gitmodules', '--list'],
                        cwd=temp_dir,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode == 0 and result.stdout:
                        submodules_path = repo_dir / "submodules.txt"
                        with open(submodules_path, 'w') as f:
                            f.write(result.stdout)
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                    pass  # No submodules or error reading them
                
                # Check for LFS
                has_lfs = await self.gitlab_client.has_lfs(project_id)
                if has_lfs:
                    lfs_info = repo_dir / "lfs_detected.txt"
                    with open(lfs_info, 'w') as f:
                        f.write("Git LFS detected. LFS objects need to be fetched separately.\n")
                
                # Build artifacts list safely
                artifacts = [str(bundle_path.relative_to(output_dir.parent))]
                if has_lfs:
                    artifacts.append(str((repo_dir / "lfs_detected.txt").relative_to(output_dir.parent)))
                
                return {
                    "success": True,
                    "artifacts": artifacts
                }
                
            finally:
                # Cleanup temporary clone
                if temp_dir.exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)
            
        except subprocess.TimeoutExpired as e:
            error = f"Repository operation timed out: {e.cmd[0] if e.cmd else 'unknown'}"
            return {"success": False, "error": error}
        except subprocess.CalledProcessError as e:
            # Sanitize error message
            error = self._sanitize_error_message(str(e.stderr), self.gitlab_client.token)
            return {"success": False, "error": f"Git command failed: {error}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _export_ci_cd(
        self,
        project_id: int,
        project: Dict[str, Any],
        output_dir: Path
    ) -> Dict[str, Any]:
        """Export CI/CD configuration"""
        try:
            ci_dir = output_dir / "ci"
            
            # Export .gitlab-ci.yml
            gitlab_ci_content = await self.gitlab_client.get_file_content(
                project_id,
                '.gitlab-ci.yml'
            )
            
            if gitlab_ci_content:
                with open(ci_dir / "gitlab-ci.yml", 'w') as f:
                    f.write(gitlab_ci_content)
            
            # Export variables metadata (not values for security)
            variables = await self.gitlab_client.list_variables(project_id)
            variables_safe = []
            for var in variables:
                variables_safe.append({
                    "key": var.get("key"),
                    "variable_type": var.get("variable_type"),
                    "protected": var.get("protected"),
                    "masked": var.get("masked"),
                    "environment_scope": var.get("environment_scope"),
                    # Note: value not exported for security
                })
            
            with open(ci_dir / "variables.json", 'w') as f:
                json.dump(variables_safe, f, indent=2)
            
            # Export environments
            environments = await self.gitlab_client.list_environments(project_id)
            with open(ci_dir / "environments.json", 'w') as f:
                json.dump(environments, f, indent=2)
            
            # Export schedules
            schedules = await self.gitlab_client.list_pipeline_schedules(project_id)
            with open(ci_dir / "schedules.json", 'w') as f:
                json.dump(schedules, f, indent=2)
            
            # Export recent pipeline history
            pipelines = await self.gitlab_client.list_pipelines(project_id, max_count=100)
            with open(ci_dir / "pipeline_history.json", 'w') as f:
                json.dump(pipelines, f, indent=2)
            
            return {
                "success": True,
                "count": len(variables) + len(environments) + len(schedules)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _export_issues(
        self,
        project_id: int,
        project: Dict[str, Any],
        output_dir: Path
    ) -> Dict[str, Any]:
        """Export all issues with comments and attachments"""
        try:
            issues_dir = output_dir / "issues"
            attachments_dir = issues_dir / "attachments"
            all_issues = []
            attachment_metadata = {}  # Maps old paths to new paths
            project_path = project.get('path_with_namespace', str(project_id))
            
            # Check if resuming
            last_processed = None
            if self.checkpoint and self.checkpoint.should_resume_component("issues"):
                last_processed = self.checkpoint.get_last_processed_item("issues")
                self.log_event("INFO", f"Resuming issues export from iid {last_processed}")
            
            skip_until_found = last_processed is not None
            
            async for issue in self.gitlab_client.list_issues(project_id):
                issue_iid = issue['iid']
                
                # Skip until we find the last processed issue
                if skip_until_found:
                    if issue_iid == last_processed:
                        skip_until_found = False
                    continue
                
                # Get full issue details
                full_issue = await self.gitlab_client.get_issue(project_id, issue_iid)
                
                # Get comments/notes
                notes = await self.gitlab_client.list_issue_notes(project_id, issue_iid)
                full_issue['notes'] = notes
                
                # Extract and download attachments from description
                attachments_found = set()
                if full_issue.get('description'):
                    attachments_found.update(self._extract_attachments(full_issue['description']))
                
                # Extract attachments from notes/comments
                for note in notes:
                    if note.get('body'):
                        attachments_found.update(self._extract_attachments(note['body']))
                
                # Download attachments
                for attachment_path in attachments_found:
                    if attachment_path not in attachment_metadata:
                        local_path = await self._download_attachment(
                            project_path,
                            attachment_path,
                            attachments_dir
                        )
                        if local_path:
                            # Store relative path for later use
                            attachment_metadata[attachment_path] = str(local_path.relative_to(output_dir))
                
                all_issues.append(full_issue)
                
                # Update checkpoint progress every 10 issues
                if len(all_issues) % 10 == 0:
                    self.log_event("INFO", f"Exported {len(all_issues)} issues...")
                    if self.checkpoint:
                        self.checkpoint.update_component_progress(
                            "issues",
                            processed_items=len(all_issues),
                            last_item=issue_iid
                        )
            
            # Save all issues
            with open(issues_dir / "issues.json", 'w') as f:
                json.dump(all_issues, f, indent=2)
            
            # Save attachment metadata mapping
            if attachment_metadata:
                with open(issues_dir / "attachment_metadata.json", 'w') as f:
                    json.dump(attachment_metadata, f, indent=2)
                self.log_event("INFO", f"Downloaded {len(attachment_metadata)} attachments for issues")
            
            return {
                "success": True,
                "count": len(all_issues)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _export_merge_requests(
        self,
        project_id: int,
        project: Dict[str, Any],
        output_dir: Path
    ) -> Dict[str, Any]:
        """Export all merge requests with discussions"""
        try:
            mrs_dir = output_dir / "merge_requests"
            attachments_dir = mrs_dir / "attachments"
            all_mrs = []
            attachment_metadata = {}  # Maps old paths to new paths
            project_path = project.get('path_with_namespace', str(project_id))
            
            # Check if resuming
            last_processed = None
            if self.checkpoint and self.checkpoint.should_resume_component("merge_requests"):
                last_processed = self.checkpoint.get_last_processed_item("merge_requests")
                self.log_event("INFO", f"Resuming MRs export from iid {last_processed}")
            
            skip_until_found = last_processed is not None
            
            async for mr in self.gitlab_client.list_merge_requests(project_id):
                mr_iid = mr['iid']
                
                # Skip until we find the last processed MR
                if skip_until_found:
                    if mr_iid == last_processed:
                        skip_until_found = False
                    continue
                
                # Get full MR details
                full_mr = await self.gitlab_client.get_merge_request(project_id, mr_iid)
                
                # Get discussions
                discussions = await self.gitlab_client.list_merge_request_discussions(project_id, mr_iid)
                full_mr['discussions'] = discussions
                
                # Get approvals
                approvals = await self.gitlab_client.list_merge_request_approvals(project_id, mr_iid)
                full_mr['approvals'] = approvals
                
                # Extract and download attachments from description
                attachments_found = set()
                if full_mr.get('description'):
                    attachments_found.update(self._extract_attachments(full_mr['description']))
                
                # Extract attachments from discussions
                for discussion in discussions:
                    for note in discussion.get('notes', []):
                        if note.get('body'):
                            attachments_found.update(self._extract_attachments(note['body']))
                
                # Download attachments
                for attachment_path in attachments_found:
                    if attachment_path not in attachment_metadata:
                        local_path = await self._download_attachment(
                            project_path,
                            attachment_path,
                            attachments_dir
                        )
                        if local_path:
                            # Store relative path for later use
                            attachment_metadata[attachment_path] = str(local_path.relative_to(output_dir))
                
                all_mrs.append(full_mr)
                
                # Update checkpoint progress every 10 MRs
                if len(all_mrs) % 10 == 0:
                    self.log_event("INFO", f"Exported {len(all_mrs)} merge requests...")
                    if self.checkpoint:
                        self.checkpoint.update_component_progress(
                            "merge_requests",
                            processed_items=len(all_mrs),
                            last_item=mr_iid
                        )
            
            # Save all MRs
            with open(mrs_dir / "merge_requests.json", 'w') as f:
                json.dump(all_mrs, f, indent=2)
            
            # Save attachment metadata mapping
            if attachment_metadata:
                with open(mrs_dir / "attachment_metadata.json", 'w') as f:
                    json.dump(attachment_metadata, f, indent=2)
                self.log_event("INFO", f"Downloaded {len(attachment_metadata)} attachments for merge requests")
            
            return {
                "success": True,
                "count": len(all_mrs)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _export_wiki(
        self,
        project_id: int,
        project: Dict[str, Any],
        output_dir: Path
    ) -> Dict[str, Any]:
        """Export wiki as git bundle"""
        try:
            wiki_dir = output_dir / "wiki"
            
            # Check if wiki is enabled
            if not project.get('wiki_enabled', False):
                with open(wiki_dir / "wiki_disabled.txt", 'w') as f:
                    f.write("Wiki is not enabled for this project.\n")
                return {"success": True, "count": 0}
            
            # Get wiki URL
            http_url = project.get('http_url_to_repo')
            if not http_url:
                return {"success": False, "error": "No repository URL found"}
            
            # Wiki URL is typically project_url + .wiki.git
            wiki_url = http_url.replace('.git', '.wiki.git')
            auth_wiki_url = wiki_url.replace('://', f'://oauth2:{self.gitlab_client.token}@')
            
            bundle_path = wiki_dir / "wiki.git"
            temp_dir = wiki_dir / "temp_wiki_clone"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            try:
                # Try to clone wiki
                result = subprocess.run(
                    ['git', 'clone', '--mirror', auth_wiki_url, str(temp_dir)],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                
                if result.returncode != 0:
                    # Wiki might be empty or not initialized
                    with open(wiki_dir / "wiki_empty.txt", 'w') as f:
                        f.write("Wiki exists but is empty or not initialized.\n")
                    return {"success": True, "count": 0}
                
                # Create bundle
                subprocess.run(
                    ['git', 'bundle', 'create', str(bundle_path), '--all'],
                    cwd=temp_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                return {"success": True, "count": 1}
                
            finally:
                # Cleanup
                import shutil
                if temp_dir.exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)
            
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Wiki clone/bundle timed out"}
        except subprocess.CalledProcessError as e:
            return {"success": False, "error": f"Git command failed: {e.stderr}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _export_releases(
        self,
        project_id: int,
        project: Dict[str, Any],
        output_dir: Path
    ) -> Dict[str, Any]:
        """Export releases and metadata"""
        try:
            releases_dir = output_dir / "releases"
            
            releases = await self.gitlab_client.list_releases(project_id)
            
            # Download release assets
            total_assets = 0
            failed_downloads = []
            
            for release in releases:
                tag_name = release.get("tag_name", "unknown")
                release_dir = releases_dir / tag_name
                release_dir.mkdir(parents=True, exist_ok=True)
                
                # Download each asset
                assets = release.get("assets", {})
                links = assets.get("links", []) if isinstance(assets, dict) else []
                
                for asset in links:
                    asset_url = asset.get("url")
                    asset_name = asset.get("name")
                    
                    if not asset_url or not asset_name:
                        continue
                    
                    asset_path = release_dir / asset_name
                    logger.info(f"Downloading release asset: {tag_name}/{asset_name}")
                    
                    success = await self.gitlab_client.download_file(
                        asset_url,
                        asset_path
                    )
                    
                    if success:
                        # Store local path for later upload
                        asset["local_path"] = str(asset_path)
                        total_assets += 1
                    else:
                        failed_downloads.append(f"{tag_name}/{asset_name}")
                        logger.warning(f"Failed to download asset: {tag_name}/{asset_name}")
            
            # Save releases metadata with local paths
            with open(releases_dir / "releases.json", 'w') as f:
                json.dump(releases, f, indent=2)
            
            result = {
                "success": True,
                "count": len(releases),
                "assets_downloaded": total_assets
            }
            
            if failed_downloads:
                result["failed_downloads"] = failed_downloads
                result["warning"] = f"Failed to download {len(failed_downloads)} assets"
            
            return result
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _export_packages(
        self,
        project_id: int,
        project: Dict[str, Any],
        output_dir: Path
    ) -> Dict[str, Any]:
        """Export package metadata"""
        try:
            packages_dir = output_dir / "packages"
            
            packages = await self.gitlab_client.list_packages(project_id)
            
            with open(packages_dir / "packages.json", 'w') as f:
                json.dump(packages, f, indent=2)
            
            return {
                "success": True,
                "count": len(packages)
            }
            
        except Exception as e:
            # Packages might not be available in all GitLab editions
            return {"success": True, "count": 0}
    
    async def _export_settings(
        self,
        project_id: int,
        project: Dict[str, Any],
        output_dir: Path
    ) -> Dict[str, Any]:
        """Export project settings and governance"""
        try:
            settings_dir = output_dir / "settings"
            
            # Export protected branches
            protected_branches = await self.gitlab_client.list_protected_branches(project_id)
            with open(settings_dir / "protected_branches.json", 'w') as f:
                json.dump(protected_branches, f, indent=2)
            
            # Export protected tags
            protected_tags = await self.gitlab_client.list_protected_tags(project_id)
            with open(settings_dir / "protected_tags.json", 'w') as f:
                json.dump(protected_tags, f, indent=2)
            
            # Export members
            members = await self.gitlab_client.list_project_members(project_id)
            with open(settings_dir / "members.json", 'w') as f:
                json.dump(members, f, indent=2)
            
            # Export webhooks (mask secrets)
            webhooks = await self.gitlab_client.list_webhooks(project_id)
            for hook in webhooks:
                if 'token' in hook:
                    hook['token'] = '***MASKED***'
            with open(settings_dir / "webhooks.json", 'w') as f:
                json.dump(webhooks, f, indent=2)
            
            # Export deploy keys (mask private keys)
            deploy_keys = await self.gitlab_client.list_deploy_keys(project_id)
            for key in deploy_keys:
                if 'key' in key:
                    # Always mask keys for security
                    full_key = key['key']
                    if len(full_key) > 30:
                        key['key'] = full_key[:15] + '...' + full_key[-15:]
                    else:
                        # For shorter keys, just show prefix
                        key['key'] = full_key[:min(10, len(full_key))] + '***MASKED***'
            with open(settings_dir / "deploy_keys.json", 'w') as f:
                json.dump(deploy_keys, f, indent=2)
            
            # Export general project settings
            project_settings = {
                "visibility": project.get("visibility"),
                "default_branch": project.get("default_branch"),
                "merge_method": project.get("merge_method"),
                "squash_option": project.get("squash_option"),
                "only_allow_merge_if_pipeline_succeeds": project.get("only_allow_merge_if_pipeline_succeeds"),
                "only_allow_merge_if_all_discussions_are_resolved": project.get("only_allow_merge_if_all_discussions_are_resolved"),
                "remove_source_branch_after_merge": project.get("remove_source_branch_after_merge"),
                "lfs_enabled": project.get("lfs_enabled"),
                "archived": project.get("archived"),
                "issues_enabled": project.get("issues_enabled"),
                "merge_requests_enabled": project.get("merge_requests_enabled"),
                "wiki_enabled": project.get("wiki_enabled"),
                "snippets_enabled": project.get("snippets_enabled"),
                "container_registry_enabled": project.get("container_registry_enabled")
            }
            with open(settings_dir / "project_settings.json", 'w') as f:
                json.dump(project_settings, f, indent=2)
            
            return {
                "success": True,
                "count": len(protected_branches) + len(members) + len(webhooks)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def generate_artifacts(self, data: Dict[str, Any]) -> Dict[str, str]:
        """Generate export artifacts"""
        return {
            "export_manifest": "export/manifest.json",
            "repo_bundle": "export/repository/bundle.git",
            "issues": "export/issues/issues.json",
            "merge_requests": "export/merge_requests/merge_requests.json",
            "ci_config": "export/ci/gitlab-ci.yml"
        }
