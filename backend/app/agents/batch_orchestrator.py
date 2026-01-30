"""Batch orchestrator for parallel migration of multiple projects"""

import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.agents.orchestrator import AgentOrchestrator, MigrationMode
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SharedResources:
    """
    Shared resources across parallel migrations.
    
    Manages resources that need to be shared across multiple
    parallel migration processes to avoid conflicts and optimize
    resource usage.
    """
    
    def __init__(self, github_rate_limit: int = 5000):
        """
        Initialize shared resources.
        
        Args:
            github_rate_limit: Maximum GitHub API calls across all parallel jobs
                              (Note: Rate limiting implementation is a future enhancement)
        """
        self.user_mapping_cache: Dict[str, Any] = {}
        # Note: Rate limiting is a placeholder for future implementation
        # Currently, rate limiting is handled at the client level
        self.github_rate_limit = github_rate_limit
        self.github_rate_limiter = None  # Reserved for future rate limiting implementation
        self._lock = asyncio.Lock()
        self.logger = get_logger(__name__)
    
    async def get_user_mapping(self, gitlab_user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached user mapping.
        
        Note: This is a placeholder for future integration. User mapping
        functionality will be integrated with the migration agents in a
        future enhancement.
        
        Args:
            gitlab_user_id: GitLab user ID
            
        Returns:
            User mapping if cached, None otherwise
        """
        async with self._lock:
            return self.user_mapping_cache.get(gitlab_user_id)
    
    async def set_user_mapping(self, gitlab_user_id: str, mapping: Dict[str, Any]):
        """
        Cache user mapping.
        
        Note: This is a placeholder for future integration. User mapping
        functionality will be integrated with the migration agents in a
        future enhancement.
        
        Args:
            gitlab_user_id: GitLab user ID
            mapping: User mapping data
        """
        async with self._lock:
            self.user_mapping_cache[gitlab_user_id] = mapping
            self.logger.debug(f"Cached user mapping for {gitlab_user_id}")
    
    def get_rate_limiter(self):
        """Get shared rate limiter"""
        return self.github_rate_limiter


class BatchOrchestrator:
    """
    Orchestrator for batch migration of multiple projects in parallel.
    
    Features:
    - Parallel execution with configurable concurrency limit
    - Shared resource management (rate limiting, user mappings)
    - Independent failure handling (one failure doesn't stop others)
    - Aggregate progress tracking
    - Per-project result tracking
    """
    
    def __init__(self, shared_resources: Optional[SharedResources] = None):
        """
        Initialize batch orchestrator.
        
        Args:
            shared_resources: Optional shared resources instance
        """
        self.logger = get_logger(__name__)
        self.shared_resources = shared_resources or SharedResources()
    
    async def execute_batch_migration(
        self,
        project_configs: List[Dict[str, Any]],
        mode: MigrationMode = MigrationMode.FULL,
        parallel_limit: int = 5,
        resume_from: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute migration for multiple projects in parallel.
        
        Args:
            project_configs: List of project configurations, each containing:
                - project_id: GitLab project ID
                - gitlab_url: GitLab instance URL
                - gitlab_token: GitLab access token
                - github_token: GitHub access token
                - output_dir: Output directory for artifacts
                - (other config as needed)
            mode: Migration mode for all projects
            parallel_limit: Maximum number of concurrent migrations
            resume_from: Optional agent to resume from
            
        Returns:
            Dict containing:
                - status: Overall batch status (success/partial_success/failed)
                - started_at: Start timestamp
                - finished_at: Finish timestamp
                - total_projects: Total number of projects
                - successful: Number of successful migrations
                - failed: Number of failed migrations
                - results: List of per-project results
        """
        self.logger.info(
            f"Starting batch migration of {len(project_configs)} projects "
            f"in {mode} mode with parallelism={parallel_limit}"
        )
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(parallel_limit)
        
        # Track results
        batch_result = {
            "status": "running",
            "mode": mode.value,
            "started_at": datetime.utcnow().isoformat(),
            "total_projects": len(project_configs),
            "parallel_limit": parallel_limit,
            "results": []
        }
        
        async def migrate_one_project(config: Dict[str, Any], index: int) -> Dict[str, Any]:
            """
            Migrate a single project with semaphore-controlled concurrency.
            
            Args:
                config: Project configuration
                index: Project index in batch
                
            Returns:
                Project migration result
            """
            project_id = config.get("project_id", f"project_{index}")
            
            async with semaphore:
                self.logger.info(f"Starting migration for project {project_id} (#{index + 1})")
                
                try:
                    # Create a new orchestrator instance for this project
                    # to avoid shared state issues
                    project_orchestrator = AgentOrchestrator()
                    
                    # Execute migration
                    result = await project_orchestrator.run_migration(
                        mode=mode,
                        config=config,
                        resume_from=resume_from
                    )
                    
                    # Add project identifier to result
                    result["project_id"] = project_id
                    result["index"] = index
                    
                    self.logger.info(
                        f"Completed migration for project {project_id}: "
                        f"status={result.get('status')}"
                    )
                    
                    return result
                    
                except Exception as e:
                    self.logger.error(
                        f"Exception during migration of project {project_id}: {str(e)}"
                    )
                    return {
                        "project_id": project_id,
                        "index": index,
                        "status": "failed",
                        "error": str(e),
                        "started_at": datetime.utcnow().isoformat(),
                        "finished_at": datetime.utcnow().isoformat()
                    }
        
        try:
            # Create tasks for all projects
            tasks = [
                migrate_one_project(config, i)
                for i, config in enumerate(project_configs)
            ]
            
            # Execute all tasks, collecting results even if some fail
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            successful = 0
            failed = 0
            
            for i, result in enumerate(results):
                # Handle exceptions that weren't caught
                if isinstance(result, Exception):
                    project_id = project_configs[i].get("project_id", f"project_{i}")
                    self.logger.error(
                        f"Unhandled exception for project {project_id}: {str(result)}"
                    )
                    result = {
                        "project_id": project_id,
                        "index": i,
                        "status": "failed",
                        "error": str(result),
                        "started_at": datetime.utcnow().isoformat(),
                        "finished_at": datetime.utcnow().isoformat()
                    }
                    failed += 1
                else:
                    # Count success/failure
                    if result.get("status") == "success":
                        successful += 1
                    else:
                        failed += 1
                
                batch_result["results"].append(result)
            
            # Update batch status
            batch_result["successful"] = successful
            batch_result["failed"] = failed
            batch_result["finished_at"] = datetime.utcnow().isoformat()
            
            # Determine overall status
            if failed == 0:
                batch_result["status"] = "success"
            elif successful > 0:
                batch_result["status"] = "partial_success"
            else:
                batch_result["status"] = "failed"
            
            self.logger.info(
                f"Batch migration completed: {successful} successful, "
                f"{failed} failed out of {len(project_configs)} total"
            )
            
        except Exception as e:
            self.logger.error(f"Batch migration failed with exception: {str(e)}")
            batch_result["status"] = "failed"
            batch_result["error"] = str(e)
            batch_result["finished_at"] = datetime.utcnow().isoformat()
        
        return batch_result
    
    async def get_progress(self) -> Dict[str, Any]:
        """
        Get current progress of batch migration.
        
        Returns:
            Dict with progress information
        """
        # This is a placeholder - in a real implementation,
        # we'd track progress in a shared state
        return {
            "status": "Not implemented - use event system for real-time progress"
        }
