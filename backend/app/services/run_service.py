"""Run service for managing migration runs"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
from pymongo.errors import PyMongoError

from app.services.base_service import BaseService
from app.models import MigrationRun, RunStats


class RunService(BaseService):
    """Service for managing migration runs"""
    
    COLLECTION = "runs"
    
    async def create_run(
        self,
        project_id: str,
        mode: str = "PLAN_ONLY",
        config: Optional[Dict[str, Any]] = None
    ) -> MigrationRun:
        """
        Create a new migration run
        
        Args:
            project_id: Project ID
            mode: Run mode (FULL, PLAN_ONLY, DISCOVER_ONLY, etc.)
            config: Optional configuration snapshot
            
        Returns:
            Created run
            
        Raises:
            ValueError: If project_id is not valid
            RuntimeError: If database operation fails
        """
        try:
            if not ObjectId.is_valid(project_id):
                raise ValueError(f"Invalid project ID: {project_id}")
            
            # Create run document
            run_dict = {
                "project_id": ObjectId(project_id),
                "mode": mode,
                "status": "CREATED",
                "stage": None,
                "started_at": None,
                "finished_at": None,
                "stats": RunStats().model_dump(),
                "config_snapshot": config or {},
                "artifact_root": None,
                "error": None,
                "created_at": datetime.utcnow()
            }
            
            # Insert into database
            result = await self.db[self.COLLECTION].insert_one(run_dict)
            run_dict["_id"] = result.inserted_id
            
            self.logger.info(f"Created run: {result.inserted_id} for project {project_id} (mode: {mode})")
            return MigrationRun(**run_dict)
            
        except PyMongoError as e:
            self.logger.error(f"Database error creating run: {e}")
            raise RuntimeError(f"Failed to create run: {str(e)}")
    
    async def get_run(self, run_id: str) -> Optional[MigrationRun]:
        """
        Get run by ID
        
        Args:
            run_id: Run ID
            
        Returns:
            Run if found, None otherwise
        """
        try:
            if not ObjectId.is_valid(run_id):
                return None
            
            run_dict = await self.db[self.COLLECTION].find_one({"_id": ObjectId(run_id)})
            if run_dict:
                return MigrationRun(**run_dict)
            return None
            
        except PyMongoError as e:
            self.logger.error(f"Database error fetching run {run_id}: {e}")
            return None
    
    async def list_runs(
        self,
        project_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None
    ) -> List[MigrationRun]:
        """
        List runs with pagination
        
        Args:
            project_id: Optional project ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return
            status: Optional status filter
            
        Returns:
            List of runs
        """
        try:
            # Build query
            query = {}
            if project_id and ObjectId.is_valid(project_id):
                query["project_id"] = ObjectId(project_id)
            if status:
                query["status"] = status
            
            # Fetch runs
            cursor = self.db[self.COLLECTION].find(query).skip(skip).limit(limit).sort("created_at", -1)
            runs = []
            async for run_dict in cursor:
                runs.append(MigrationRun(**run_dict))
            return runs
            
        except PyMongoError as e:
            self.logger.error(f"Database error listing runs: {e}")
            return []
    
    async def update_run_status(
        self,
        run_id: str,
        status: str,
        stage: Optional[str] = None,
        error: Optional[Dict[str, str]] = None
    ) -> Optional[MigrationRun]:
        """
        Update run status and stage
        
        Args:
            run_id: Run ID
            status: New status
            stage: Optional new stage
            error: Optional error information
            
        Returns:
            Updated run if found, None otherwise
        """
        try:
            if not ObjectId.is_valid(run_id):
                return None
            
            # Build update document
            updates = {"status": status}
            
            if stage is not None:
                updates["stage"] = stage
            
            if error is not None:
                updates["error"] = error
            
            # Set timestamps based on status
            if status == "RUNNING" and stage:
                updates["started_at"] = datetime.utcnow()
            elif status in ["COMPLETED", "FAILED", "CANCELED"]:
                updates["finished_at"] = datetime.utcnow()
            
            # Update run
            result = await self.db[self.COLLECTION].find_one_and_update(
                {"_id": ObjectId(run_id)},
                {"$set": updates},
                return_document=True
            )
            
            if result:
                self.logger.info(f"Updated run {run_id} status to {status}")
                return MigrationRun(**result)
            return None
            
        except PyMongoError as e:
            self.logger.error(f"Database error updating run {run_id}: {e}")
            return None
    
    async def update_run_stats(self, run_id: str, stats_updates: Dict[str, int]) -> Optional[MigrationRun]:
        """
        Update run statistics
        
        Args:
            run_id: Run ID
            stats_updates: Dictionary of stats to update
            
        Returns:
            Updated run if found, None otherwise
        """
        try:
            if not ObjectId.is_valid(run_id):
                return None
            
            # Build nested stats update
            stats_update = {f"stats.{key}": value for key, value in stats_updates.items()}
            
            # Update run
            result = await self.db[self.COLLECTION].find_one_and_update(
                {"_id": ObjectId(run_id)},
                {"$set": stats_update},
                return_document=True
            )
            
            if result:
                return MigrationRun(**result)
            return None
            
        except PyMongoError as e:
            self.logger.error(f"Database error updating run stats {run_id}: {e}")
            return None
    
    async def increment_run_stats(self, run_id: str, field: str, amount: int = 1) -> bool:
        """
        Increment a run statistics field
        
        Args:
            run_id: Run ID
            field: Stats field to increment (e.g., 'groups', 'projects', 'errors', 'api_calls')
            amount: Amount to increment (default: 1)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not ObjectId.is_valid(run_id):
                return False
            
            result = await self.db[self.COLLECTION].update_one(
                {"_id": ObjectId(run_id)},
                {"$inc": {f"stats.{field}": amount}}
            )
            
            return result.modified_count > 0
            
        except PyMongoError as e:
            self.logger.error(f"Database error incrementing run stats {run_id}: {e}")
            return False
    
    async def cancel_run(self, run_id: str) -> Optional[MigrationRun]:
        """
        Cancel a run
        
        Args:
            run_id: Run ID
            
        Returns:
            Updated run if found, None otherwise
        """
        return await self.update_run_status(run_id, "CANCELED")
    
    async def resume_run(self, run_id: str, from_stage: Optional[str] = None) -> Optional[MigrationRun]:
        """
        Resume a failed or cancelled run
        
        Args:
            run_id: Run ID
            from_stage: Optional stage to resume from
            
        Returns:
            Updated run if found, None otherwise
        """
        try:
            if not ObjectId.is_valid(run_id):
                return None
            
            # Get current run
            run = await self.get_run(run_id)
            if not run:
                return None
            
            # Can only resume failed or cancelled runs
            if run.status not in ["FAILED", "CANCELED"]:
                self.logger.warning(f"Cannot resume run {run_id} with status {run.status}")
                return None
            
            # Update status and optionally stage
            updates = {
                "status": "QUEUED",
                "error": None,
                "finished_at": None
            }
            
            if from_stage:
                updates["stage"] = from_stage
            
            result = await self.db[self.COLLECTION].find_one_and_update(
                {"_id": ObjectId(run_id)},
                {"$set": updates},
                return_document=True
            )
            
            if result:
                self.logger.info(f"Resumed run {run_id}")
                return MigrationRun(**result)
            return None
            
        except PyMongoError as e:
            self.logger.error(f"Database error resuming run {run_id}: {e}")
            return None
    
    async def set_artifact_root(self, run_id: str, artifact_root: str) -> bool:
        """
        Set artifact root path for a run
        
        Args:
            run_id: Run ID
            artifact_root: Path to artifact root
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not ObjectId.is_valid(run_id):
                return False
            
            result = await self.db[self.COLLECTION].update_one(
                {"_id": ObjectId(run_id)},
                {"$set": {"artifact_root": artifact_root}}
            )
            
            return result.modified_count > 0
            
        except PyMongoError as e:
            self.logger.error(f"Database error setting artifact root for run {run_id}: {e}")
            return False
    
    async def ensure_indexes(self):
        """Create necessary indexes for runs collection"""
        try:
            await self.db[self.COLLECTION].create_index("project_id")
            await self.db[self.COLLECTION].create_index("status")
            await self.db[self.COLLECTION].create_index("created_at")
            self.logger.info("Run indexes created")
        except PyMongoError as e:
            self.logger.error(f"Error creating run indexes: {e}")
