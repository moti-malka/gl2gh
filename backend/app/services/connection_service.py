"""Connection service for managing GitLab/GitHub credentials"""

from typing import Optional, List
from datetime import datetime
from bson import ObjectId
from pymongo.errors import PyMongoError

from app.services.base_service import BaseService
from app.models import Connection
from app.utils.security import encrypt_token, decrypt_token, get_token_last4


class ConnectionService(BaseService):
    """Service for managing connections (credentials)"""
    
    COLLECTION = "connections"
    
    async def store_gitlab_connection(
        self,
        project_id: str,
        token: str,
        base_url: Optional[str] = None
    ) -> Connection:
        """
        Store GitLab connection
        
        Args:
            project_id: Project ID
            token: GitLab personal access token
            base_url: Optional GitLab base URL (default: https://gitlab.com)
            
        Returns:
            Created connection
            
        Raises:
            ValueError: If project_id is not valid
            RuntimeError: If database operation fails
        """
        return await self._store_connection(project_id, "gitlab", token, base_url)
    
    async def store_github_connection(
        self,
        project_id: str,
        token: str,
        base_url: Optional[str] = None
    ) -> Connection:
        """
        Store GitHub connection
        
        Args:
            project_id: Project ID
            token: GitHub personal access token
            base_url: Optional GitHub base URL (default: https://api.github.com)
            
        Returns:
            Created connection
            
        Raises:
            ValueError: If project_id is not valid
            RuntimeError: If database operation fails
        """
        return await self._store_connection(project_id, "github", token, base_url)
    
    async def _store_connection(
        self,
        project_id: str,
        conn_type: str,
        token: str,
        base_url: Optional[str] = None
    ) -> Connection:
        """
        Store connection (internal method)
        
        Args:
            project_id: Project ID
            conn_type: Connection type (gitlab or github)
            token: Personal access token
            base_url: Optional base URL
            
        Returns:
            Created connection
            
        Raises:
            ValueError: If project_id is not valid
            RuntimeError: If database operation fails
        """
        try:
            if not ObjectId.is_valid(project_id):
                raise ValueError(f"Invalid project ID: {project_id}")
            
            # Encrypt token
            token_encrypted = encrypt_token(token)
            token_last4 = get_token_last4(token)
            
            # Delete existing connection of same type for this project
            await self.db[self.COLLECTION].delete_many({
                "project_id": ObjectId(project_id),
                "type": conn_type
            })
            
            # Create connection document
            connection_dict = {
                "project_id": ObjectId(project_id),
                "type": conn_type,
                "base_url": base_url,
                "token_encrypted": token_encrypted,
                "token_last4": token_last4,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            # Insert into database
            result = await self.db[self.COLLECTION].insert_one(connection_dict)
            connection_dict["_id"] = result.inserted_id
            
            self.logger.info(f"Stored {conn_type} connection for project {project_id} (last4: {token_last4})")
            return Connection(**connection_dict)
            
        except PyMongoError as e:
            self.logger.error(f"Database error storing connection: {e}")
            raise RuntimeError(f"Failed to store connection: {str(e)}")
    
    async def get_connections(self, project_id: str) -> List[Connection]:
        """
        Get all connections for a project
        
        Args:
            project_id: Project ID
            
        Returns:
            List of connections
        """
        try:
            if not ObjectId.is_valid(project_id):
                return []
            
            cursor = self.db[self.COLLECTION].find({"project_id": ObjectId(project_id)})
            connections = []
            async for conn_dict in cursor:
                connections.append(Connection(**conn_dict))
            return connections
            
        except PyMongoError as e:
            self.logger.error(f"Database error fetching connections for project {project_id}: {e}")
            return []
    
    async def get_connection_by_type(self, project_id: str, conn_type: str) -> Optional[Connection]:
        """
        Get connection by project ID and type
        
        Args:
            project_id: Project ID
            conn_type: Connection type (gitlab or github)
            
        Returns:
            Connection if found, None otherwise
        """
        try:
            if not ObjectId.is_valid(project_id):
                return None
            
            conn_dict = await self.db[self.COLLECTION].find_one({
                "project_id": ObjectId(project_id),
                "type": conn_type
            })
            
            if conn_dict:
                return Connection(**conn_dict)
            return None
            
        except PyMongoError as e:
            self.logger.error(f"Database error fetching {conn_type} connection for project {project_id}: {e}")
            return None
    
    async def get_decrypted_token(self, connection_id: str) -> Optional[str]:
        """
        Get decrypted token from connection
        
        Args:
            connection_id: Connection ID
            
        Returns:
            Decrypted token if found, None otherwise
        """
        try:
            if not ObjectId.is_valid(connection_id):
                return None
            
            conn_dict = await self.db[self.COLLECTION].find_one({"_id": ObjectId(connection_id)})
            if conn_dict:
                token = decrypt_token(conn_dict["token_encrypted"])
                self.logger.debug(f"Decrypted token for connection {connection_id}")
                return token
            return None
            
        except PyMongoError as e:
            self.logger.error(f"Database error fetching connection {connection_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error decrypting token for connection {connection_id}: {e}")
            return None
    
    async def delete_connection(self, connection_id: str) -> bool:
        """
        Delete connection
        
        Args:
            connection_id: Connection ID
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            if not ObjectId.is_valid(connection_id):
                return False
            
            result = await self.db[self.COLLECTION].delete_one({"_id": ObjectId(connection_id)})
            
            if result.deleted_count > 0:
                self.logger.info(f"Deleted connection: {connection_id}")
                return True
            return False
            
        except PyMongoError as e:
            self.logger.error(f"Database error deleting connection {connection_id}: {e}")
            return False
    
    async def delete_project_connections(self, project_id: str) -> int:
        """
        Delete all connections for a project
        
        Args:
            project_id: Project ID
            
        Returns:
            Number of connections deleted
        """
        try:
            if not ObjectId.is_valid(project_id):
                return 0
            
            result = await self.db[self.COLLECTION].delete_many({"project_id": ObjectId(project_id)})
            count = result.deleted_count
            
            if count > 0:
                self.logger.info(f"Deleted {count} connections for project {project_id}")
            return count
            
        except PyMongoError as e:
            self.logger.error(f"Database error deleting connections for project {project_id}: {e}")
            return 0
    
    async def ensure_indexes(self):
        """Create necessary indexes for connections collection"""
        try:
            await self.db[self.COLLECTION].create_index([("project_id", 1), ("type", 1)], unique=True)
            self.logger.info("Connection indexes created")
        except PyMongoError as e:
            self.logger.error(f"Error creating connection indexes: {e}")
