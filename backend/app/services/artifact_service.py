"""Artifact service for managing migration artifacts"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
from pymongo.errors import PyMongoError

from app.services.base_service import BaseService
from app.models import Artifact


class ArtifactService(BaseService):
    """Service for managing migration artifacts"""
    
    COLLECTION = "artifacts"
    
    async def store_artifact(
        self,
        run_id: str,
        artifact_type: str,
        path: str,
        project_id: Optional[str] = None,
        gitlab_project_id: Optional[int] = None,
        size_bytes: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Artifact:
        """
        Store artifact metadata
        
        Args:
            run_id: Run ID
            artifact_type: Type of artifact (inventory, plan, apply_report, etc.)
            path: Relative path from artifact_root
            project_id: Optional project ID
            gitlab_project_id: Optional GitLab project ID
            size_bytes: Optional file size in bytes
            metadata: Optional additional metadata
            
        Returns:
            Created artifact
            
        Raises:
            ValueError: If run_id is not valid
            RuntimeError: If database operation fails
        """
        try:
            if not ObjectId.is_valid(run_id):
                raise ValueError(f"Invalid run ID: {run_id}")
            
            # Build artifact document
            artifact_dict = {
                "run_id": ObjectId(run_id),
                "type": artifact_type,
                "path": path,
                "gitlab_project_id": gitlab_project_id,
                "size_bytes": size_bytes,
                "created_at": datetime.utcnow(),
                "metadata": metadata or {}
            }
            
            # Add project_id if provided and valid
            if project_id and ObjectId.is_valid(project_id):
                artifact_dict["project_id"] = ObjectId(project_id)
            else:
                artifact_dict["project_id"] = None
            
            # Insert into database
            result = await self.db[self.COLLECTION].insert_one(artifact_dict)
            artifact_dict["_id"] = result.inserted_id
            
            self.logger.info(f"Stored artifact: {artifact_type} at {path} for run {run_id}")
            return Artifact(**artifact_dict)
            
        except PyMongoError as e:
            self.logger.error(f"Database error storing artifact: {e}")
            raise RuntimeError(f"Failed to store artifact: {str(e)}")
    
    async def get_artifact(self, artifact_id: str) -> Optional[Artifact]:
        """
        Get artifact by ID
        
        Args:
            artifact_id: Artifact ID
            
        Returns:
            Artifact if found, None otherwise
        """
        try:
            if not ObjectId.is_valid(artifact_id):
                return None
            
            artifact_dict = await self.db[self.COLLECTION].find_one({"_id": ObjectId(artifact_id)})
            if artifact_dict:
                return Artifact(**artifact_dict)
            return None
            
        except PyMongoError as e:
            self.logger.error(f"Database error fetching artifact {artifact_id}: {e}")
            return None
    
    async def list_artifacts(
        self,
        run_id: str,
        artifact_type: Optional[str] = None,
        gitlab_project_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 1000
    ) -> List[Artifact]:
        """
        List artifacts for a run
        
        Args:
            run_id: Run ID
            artifact_type: Optional filter by artifact type
            gitlab_project_id: Optional filter by GitLab project ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of artifacts
        """
        try:
            if not ObjectId.is_valid(run_id):
                return []
            
            # Build query
            query = {"run_id": ObjectId(run_id)}
            
            if artifact_type:
                query["type"] = artifact_type
            
            if gitlab_project_id is not None:
                query["gitlab_project_id"] = gitlab_project_id
            
            # Fetch artifacts
            cursor = self.db[self.COLLECTION].find(query).skip(skip).limit(limit).sort("created_at", -1)
            artifacts = []
            async for artifact_dict in cursor:
                artifacts.append(Artifact(**artifact_dict))
            return artifacts
            
        except PyMongoError as e:
            self.logger.error(f"Database error listing artifacts for run {run_id}: {e}")
            return []
    
    async def get_artifact_by_path(self, run_id: str, path: str) -> Optional[Artifact]:
        """
        Get artifact by run ID and path
        
        Args:
            run_id: Run ID
            path: Artifact path
            
        Returns:
            Artifact if found, None otherwise
        """
        try:
            if not ObjectId.is_valid(run_id):
                return None
            
            artifact_dict = await self.db[self.COLLECTION].find_one({
                "run_id": ObjectId(run_id),
                "path": path
            })
            
            if artifact_dict:
                return Artifact(**artifact_dict)
            return None
            
        except PyMongoError as e:
            self.logger.error(f"Database error fetching artifact by path {path}: {e}")
            return None
    
    async def update_artifact_metadata(
        self,
        artifact_id: str,
        metadata: Dict[str, Any]
    ) -> Optional[Artifact]:
        """
        Update artifact metadata
        
        Args:
            artifact_id: Artifact ID
            metadata: Metadata to update
            
        Returns:
            Updated artifact if found, None otherwise
        """
        try:
            if not ObjectId.is_valid(artifact_id):
                return None
            
            result = await self.db[self.COLLECTION].find_one_and_update(
                {"_id": ObjectId(artifact_id)},
                {"$set": {"metadata": metadata}},
                return_document=True
            )
            
            if result:
                self.logger.info(f"Updated artifact metadata: {artifact_id}")
                return Artifact(**result)
            return None
            
        except PyMongoError as e:
            self.logger.error(f"Database error updating artifact {artifact_id}: {e}")
            return None
    
    async def count_artifacts(
        self,
        run_id: str,
        artifact_type: Optional[str] = None
    ) -> int:
        """
        Count artifacts for a run
        
        Args:
            run_id: Run ID
            artifact_type: Optional filter by artifact type
            
        Returns:
            Number of artifacts
        """
        try:
            if not ObjectId.is_valid(run_id):
                return 0
            
            query = {"run_id": ObjectId(run_id)}
            if artifact_type:
                query["type"] = artifact_type
            
            count = await self.db[self.COLLECTION].count_documents(query)
            return count
            
        except PyMongoError as e:
            self.logger.error(f"Database error counting artifacts for run {run_id}: {e}")
            return 0
    
    async def delete_artifact(self, artifact_id: str) -> bool:
        """
        Delete artifact metadata
        
        Args:
            artifact_id: Artifact ID
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            if not ObjectId.is_valid(artifact_id):
                return False
            
            result = await self.db[self.COLLECTION].delete_one({"_id": ObjectId(artifact_id)})
            
            if result.deleted_count > 0:
                self.logger.info(f"Deleted artifact: {artifact_id}")
                return True
            return False
            
        except PyMongoError as e:
            self.logger.error(f"Database error deleting artifact {artifact_id}: {e}")
            return False
    
    async def delete_run_artifacts(self, run_id: str) -> int:
        """
        Delete all artifacts for a run
        
        Args:
            run_id: Run ID
            
        Returns:
            Number of artifacts deleted
        """
        try:
            if not ObjectId.is_valid(run_id):
                return 0
            
            result = await self.db[self.COLLECTION].delete_many({"run_id": ObjectId(run_id)})
            count = result.deleted_count
            
            if count > 0:
                self.logger.info(f"Deleted {count} artifacts for run {run_id}")
            return count
            
        except PyMongoError as e:
            self.logger.error(f"Database error deleting artifacts for run {run_id}: {e}")
            return 0
    
    async def ensure_indexes(self):
        """Create necessary indexes for artifacts collection"""
        try:
            await self.db[self.COLLECTION].create_index("run_id")
            await self.db[self.COLLECTION].create_index([("run_id", 1), ("type", 1)])
            await self.db[self.COLLECTION].create_index([("run_id", 1), ("path", 1)], unique=True)
            self.logger.info("Artifact indexes created")
        except PyMongoError as e:
            self.logger.error(f"Error creating artifact indexes: {e}")
