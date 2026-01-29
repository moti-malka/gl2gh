"""User mapping service for GitLab to GitHub user mappings"""

from typing import Optional, List
from datetime import datetime
from bson import ObjectId
from pymongo.errors import PyMongoError

from app.services.base_service import BaseService
from app.models import UserMapping


class UserMappingService(BaseService):
    """Service for managing GitLab to GitHub user mappings"""
    
    COLLECTION = "user_mappings"
    
    async def store_mapping(
        self,
        run_id: str,
        gitlab_username: str,
        github_username: Optional[str] = None,
        gitlab_email: Optional[str] = None,
        confidence: float = 0.0,
        is_manual: bool = False
    ) -> UserMapping:
        """
        Store a user mapping
        
        Args:
            run_id: Run ID
            gitlab_username: GitLab username
            github_username: Optional GitHub username
            gitlab_email: Optional GitLab email
            confidence: Confidence score (0.0 to 1.0)
            is_manual: Whether mapping was manually set
            
        Returns:
            Created or updated user mapping
            
        Raises:
            ValueError: If run_id is not valid
            RuntimeError: If database operation fails
        """
        try:
            if not ObjectId.is_valid(run_id):
                raise ValueError(f"Invalid run ID: {run_id}")
            
            # Check if mapping already exists
            existing = await self.db[self.COLLECTION].find_one({
                "run_id": ObjectId(run_id),
                "gitlab_username": gitlab_username
            })
            
            if existing:
                # Update existing mapping
                updates = {
                    "github_username": github_username,
                    "confidence": confidence,
                    "is_manual": is_manual,
                    "updated_at": datetime.utcnow()
                }
                
                if gitlab_email:
                    updates["gitlab_email"] = gitlab_email
                
                result = await self.db[self.COLLECTION].find_one_and_update(
                    {"_id": existing["_id"]},
                    {"$set": updates},
                    return_document=True
                )
                
                self.logger.info(f"Updated user mapping for {gitlab_username} -> {github_username}")
                return UserMapping(**result)
            else:
                # Create new mapping
                mapping_dict = {
                    "run_id": ObjectId(run_id),
                    "gitlab_username": gitlab_username,
                    "gitlab_email": gitlab_email,
                    "github_username": github_username,
                    "confidence": confidence,
                    "is_manual": is_manual,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
                
                result = await self.db[self.COLLECTION].insert_one(mapping_dict)
                mapping_dict["_id"] = result.inserted_id
                
                self.logger.info(f"Created user mapping for {gitlab_username} -> {github_username}")
                return UserMapping(**mapping_dict)
                
        except PyMongoError as e:
            self.logger.error(f"Database error storing user mapping: {e}")
            raise RuntimeError(f"Failed to store user mapping: {str(e)}")
    
    async def get_mappings(self, run_id: str, skip: int = 0, limit: int = 1000) -> List[UserMapping]:
        """
        Get all user mappings for a run
        
        Args:
            run_id: Run ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of user mappings
        """
        try:
            if not ObjectId.is_valid(run_id):
                return []
            
            cursor = self.db[self.COLLECTION].find(
                {"run_id": ObjectId(run_id)}
            ).skip(skip).limit(limit).sort("gitlab_username", 1)
            
            mappings = []
            async for mapping_dict in cursor:
                mappings.append(UserMapping(**mapping_dict))
            return mappings
            
        except PyMongoError as e:
            self.logger.error(f"Database error fetching user mappings for run {run_id}: {e}")
            return []
    
    async def get_mapping(self, run_id: str, gitlab_username: str) -> Optional[UserMapping]:
        """
        Get a specific user mapping
        
        Args:
            run_id: Run ID
            gitlab_username: GitLab username
            
        Returns:
            User mapping if found, None otherwise
        """
        try:
            if not ObjectId.is_valid(run_id):
                return None
            
            mapping_dict = await self.db[self.COLLECTION].find_one({
                "run_id": ObjectId(run_id),
                "gitlab_username": gitlab_username
            })
            
            if mapping_dict:
                return UserMapping(**mapping_dict)
            return None
            
        except PyMongoError as e:
            self.logger.error(f"Database error fetching mapping for {gitlab_username}: {e}")
            return None
    
    async def update_mapping(
        self,
        mapping_id: str,
        github_username: Optional[str] = None,
        is_manual: bool = True,
        confidence: Optional[float] = None
    ) -> Optional[UserMapping]:
        """
        Update a user mapping
        
        Args:
            mapping_id: Mapping ID
            github_username: New GitHub username
            is_manual: Whether this is a manual update
            confidence: Optional new confidence score
            
        Returns:
            Updated mapping if found, None otherwise
        """
        try:
            if not ObjectId.is_valid(mapping_id):
                return None
            
            updates = {
                "is_manual": is_manual,
                "updated_at": datetime.utcnow()
            }
            
            if github_username is not None:
                updates["github_username"] = github_username
            
            if confidence is not None:
                updates["confidence"] = confidence
            
            result = await self.db[self.COLLECTION].find_one_and_update(
                {"_id": ObjectId(mapping_id)},
                {"$set": updates},
                return_document=True
            )
            
            if result:
                self.logger.info(f"Updated user mapping {mapping_id}")
                return UserMapping(**result)
            return None
            
        except PyMongoError as e:
            self.logger.error(f"Database error updating mapping {mapping_id}: {e}")
            return None
    
    async def get_unmapped_users(self, run_id: str) -> List[UserMapping]:
        """
        Get all unmapped GitLab users
        
        Args:
            run_id: Run ID
            
        Returns:
            List of unmapped user mappings
        """
        try:
            if not ObjectId.is_valid(run_id):
                return []
            
            cursor = self.db[self.COLLECTION].find({
                "run_id": ObjectId(run_id),
                "github_username": None
            }).sort("gitlab_username", 1)
            
            mappings = []
            async for mapping_dict in cursor:
                mappings.append(UserMapping(**mapping_dict))
            return mappings
            
        except PyMongoError as e:
            self.logger.error(f"Database error fetching unmapped users for run {run_id}: {e}")
            return []
    
    async def count_mappings(self, run_id: str, mapped_only: bool = False) -> int:
        """
        Count user mappings
        
        Args:
            run_id: Run ID
            mapped_only: If True, count only mapped users
            
        Returns:
            Number of mappings
        """
        try:
            if not ObjectId.is_valid(run_id):
                return 0
            
            query = {"run_id": ObjectId(run_id)}
            if mapped_only:
                query["github_username"] = {"$ne": None}
            
            count = await self.db[self.COLLECTION].count_documents(query)
            return count
            
        except PyMongoError as e:
            self.logger.error(f"Database error counting mappings for run {run_id}: {e}")
            return 0
    
    async def delete_run_mappings(self, run_id: str) -> int:
        """
        Delete all user mappings for a run
        
        Args:
            run_id: Run ID
            
        Returns:
            Number of mappings deleted
        """
        try:
            if not ObjectId.is_valid(run_id):
                return 0
            
            result = await self.db[self.COLLECTION].delete_many({"run_id": ObjectId(run_id)})
            count = result.deleted_count
            
            if count > 0:
                self.logger.info(f"Deleted {count} user mappings for run {run_id}")
            return count
            
        except PyMongoError as e:
            self.logger.error(f"Database error deleting mappings for run {run_id}: {e}")
            return 0
    
    async def ensure_indexes(self):
        """Create necessary indexes for user_mappings collection"""
        try:
            await self.db[self.COLLECTION].create_index([("run_id", 1), ("gitlab_username", 1)], unique=True)
            await self.db[self.COLLECTION].create_index("run_id")
            self.logger.info("User mapping indexes created")
        except PyMongoError as e:
            self.logger.error(f"Error creating user mapping indexes: {e}")
