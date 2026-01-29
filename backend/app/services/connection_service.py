"""Connection service for managing GitLab/GitHub credentials"""

from typing import Optional, List
from datetime import datetime
from bson import ObjectId
from pymongo.errors import PyMongoError

from app.services.base_service import BaseService
from app.models import Connection, MigrationProject
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
        Get all connections for a project from both connections collection and project settings
        
        Args:
            project_id: Project ID
            
        Returns:
            List of connections (merged from connections collection and project settings)
        """
        try:
            if not ObjectId.is_valid(project_id):
                return []
            
            # Get connections from connections collection
            cursor = self.db[self.COLLECTION].find({"project_id": ObjectId(project_id)})
            connections = []
            connection_types = set()  # Track which types we have from connections collection
            
            async for conn_dict in cursor:
                conn = Connection(**conn_dict)
                connections.append(conn)
                connection_types.add(conn.type)
            
            # Also check project settings for credentials not in connections collection
            project_dict = await self.db["projects"].find_one({"_id": ObjectId(project_id)})
            if project_dict:
                project = MigrationProject(**project_dict)
                
                # Check GitLab credentials in settings
                if "gitlab" not in connection_types and project.settings.gitlab:
                    gitlab_conn = self._create_connection_from_settings(
                        project_id, "gitlab", project.settings.gitlab
                    )
                    if gitlab_conn:
                        connections.append(gitlab_conn)
                
                # Check GitHub credentials in settings
                if "github" not in connection_types and project.settings.github:
                    github_conn = self._create_connection_from_settings(
                        project_id, "github", project.settings.github
                    )
                    if github_conn:
                        connections.append(github_conn)
            
            return connections
            
        except PyMongoError as e:
            self.logger.error(f"Database error fetching connections for project {project_id}: {e}")
            return []
    
    def _create_connection_from_settings(
        self,
        project_id: str,
        conn_type: str,
        settings: dict
    ) -> Optional[Connection]:
        """
        Create a Connection object from project settings
        
        Args:
            project_id: Project ID
            conn_type: Connection type (gitlab or github)
            settings: Settings dictionary containing token and optional base_url
            
        Returns:
            Connection object if token is present, None otherwise
        """
        try:
            # Check if token exists in settings
            token = settings.get("token")
            if not token:
                return None
            
            # Extract base_url if present
            base_url = settings.get("url") or settings.get("base_url")
            
            # Create a pseudo-connection object (without actual database ID)
            # Note: We use a fake ObjectId as placeholder since these aren't in the connections collection
            connection_dict = {
                "_id": ObjectId(),  # Temporary ID for response serialization
                "project_id": ObjectId(project_id),
                "type": conn_type,
                "base_url": base_url,
                "token_encrypted": encrypt_token(token),
                "token_last4": get_token_last4(token),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            return Connection(**connection_dict)
            
        except Exception as e:
            self.logger.warning(f"Error creating connection from settings: {e}")
            return None
    
    async def get_connection_by_type(self, project_id: str, conn_type: str) -> Optional[Connection]:
        """
        Get connection by project ID and type from both connections collection and project settings
        
        Args:
            project_id: Project ID
            conn_type: Connection type (gitlab or github)
            
        Returns:
            Connection if found, None otherwise
        """
        try:
            if not ObjectId.is_valid(project_id):
                return None
            
            # First check connections collection
            conn_dict = await self.db[self.COLLECTION].find_one({
                "project_id": ObjectId(project_id),
                "type": conn_type
            })
            
            if conn_dict:
                return Connection(**conn_dict)
            
            # If not found in connections collection, check project settings
            project_dict = await self.db["projects"].find_one({"_id": ObjectId(project_id)})
            if project_dict:
                project = MigrationProject(**project_dict)
                
                # Check for credentials in settings based on type
                if conn_type == "gitlab" and project.settings.gitlab:
                    return self._create_connection_from_settings(
                        project_id, "gitlab", project.settings.gitlab
                    )
                elif conn_type == "github" and project.settings.github:
                    return self._create_connection_from_settings(
                        project_id, "github", project.settings.github
                    )
            
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
