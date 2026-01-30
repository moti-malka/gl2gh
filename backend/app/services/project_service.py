"""Project service for managing migration projects"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
from pymongo.errors import PyMongoError

from app.services.base_service import BaseService
from app.models import MigrationProject, ProjectSettings


class ProjectService(BaseService):
    """Service for managing migration projects"""
    
    COLLECTION = "projects"
    
    async def create_project(
        self,
        name: str,
        created_by: str,
        description: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None
    ) -> MigrationProject:
        """
        Create a new migration project
        
        Args:
            name: Project name
            created_by: User ID who created the project
            description: Optional project description
            settings: Optional project settings
            
        Returns:
            Created project
            
        Raises:
            ValueError: If created_by is not a valid ObjectId
            RuntimeError: If database operation fails
        """
        try:
            if not ObjectId.is_valid(created_by):
                raise ValueError(f"Invalid user ID: {created_by}")
            
            # Create settings object
            project_settings = ProjectSettings(**(settings or {}))
            
            # Create project document
            project_dict = {
                "name": name,
                "description": description,
                "created_by": ObjectId(created_by),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "settings": project_settings.model_dump(),
                "status": "active"
            }
            
            # Insert into database
            result = await self.db[self.COLLECTION].insert_one(project_dict)
            project_dict["_id"] = result.inserted_id
            
            self.logger.info(f"Created project: {name} (ID: {result.inserted_id})")
            return MigrationProject(**project_dict)
            
        except PyMongoError as e:
            self.logger.error(f"Database error creating project: {e}")
            raise RuntimeError(f"Failed to create project: {str(e)}")
    
    async def get_project(self, project_id: str) -> Optional[MigrationProject]:
        """
        Get project by ID
        
        Args:
            project_id: Project ID
            
        Returns:
            Project if found, None otherwise
        """
        try:
            if not ObjectId.is_valid(project_id):
                return None
            
            project_dict = await self.db[self.COLLECTION].find_one({"_id": ObjectId(project_id)})
            if project_dict:
                return MigrationProject(**project_dict)
            return None
            
        except PyMongoError as e:
            self.logger.error(f"Database error fetching project {project_id}: {e}")
            return None
    
    async def list_projects(
        self,
        user_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        include_archived: bool = False
    ) -> List[MigrationProject]:
        """
        List projects with pagination
        
        Args:
            user_id: Optional user ID to filter by creator
            skip: Number of records to skip
            limit: Maximum number of records to return
            status: Optional status filter (active, archived)
            include_archived: Whether to include archived (deleted) projects
            
        Returns:
            List of projects
        """
        try:
            # Build query
            query = {}
            if user_id and ObjectId.is_valid(user_id):
                query["created_by"] = ObjectId(user_id)
            if status:
                query["status"] = status
            elif not include_archived:
                # By default, exclude archived projects
                query["status"] = {"$ne": "archived"}
            
            # Fetch projects
            cursor = self.db[self.COLLECTION].find(query).skip(skip).limit(limit).sort("created_at", -1)
            projects = []
            async for project_dict in cursor:
                projects.append(MigrationProject(**project_dict))
            return projects
            
        except PyMongoError as e:
            self.logger.error(f"Database error listing projects: {e}")
            return []
    
    async def update_project(self, project_id: str, updates: Dict[str, Any]) -> Optional[MigrationProject]:
        """
        Update project
        
        Args:
            project_id: Project ID
            updates: Dictionary of fields to update
            
        Returns:
            Updated project if found, None otherwise
        """
        try:
            if not ObjectId.is_valid(project_id):
                return None
            
            # Add updated_at timestamp
            updates["updated_at"] = datetime.utcnow()
            
            # Update project
            result = await self.db[self.COLLECTION].find_one_and_update(
                {"_id": ObjectId(project_id)},
                {"$set": updates},
                return_document=True
            )
            
            if result:
                self.logger.info(f"Updated project: {project_id}")
                return MigrationProject(**result)
            return None
            
        except PyMongoError as e:
            self.logger.error(f"Database error updating project {project_id}: {e}")
            return None
    
    async def delete_project(self, project_id: str) -> bool:
        """
        Delete project (soft delete by setting status to archived)
        
        Args:
            project_id: Project ID
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            if not ObjectId.is_valid(project_id):
                return False
            
            # Soft delete by updating status
            result = await self.db[self.COLLECTION].update_one(
                {"_id": ObjectId(project_id)},
                {"$set": {"status": "archived", "updated_at": datetime.utcnow()}}
            )
            
            if result.modified_count > 0:
                self.logger.info(f"Archived project: {project_id}")
                return True
            return False
            
        except PyMongoError as e:
            self.logger.error(f"Database error deleting project {project_id}: {e}")
            return False
    
    async def count_projects(self, user_id: Optional[str] = None, status: Optional[str] = None) -> int:
        """
        Count projects
        
        Args:
            user_id: Optional user ID to filter by creator
            status: Optional status filter
            
        Returns:
            Number of projects
        """
        try:
            query = {}
            if user_id and ObjectId.is_valid(user_id):
                query["created_by"] = ObjectId(user_id)
            if status:
                query["status"] = status
            
            count = await self.db[self.COLLECTION].count_documents(query)
            return count
            
        except PyMongoError as e:
            self.logger.error(f"Database error counting projects: {e}")
            return 0
    
    async def ensure_indexes(self):
        """Create necessary indexes for projects collection"""
        try:
            await self.db[self.COLLECTION].create_index("created_by")
            await self.db[self.COLLECTION].create_index("status")
            await self.db[self.COLLECTION].create_index("created_at")
            self.logger.info("Project indexes created")
        except PyMongoError as e:
            self.logger.error(f"Error creating project indexes: {e}")
