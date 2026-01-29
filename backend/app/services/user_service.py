"""User service for managing users"""

from typing import Optional, List
from datetime import datetime
from bson import ObjectId
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.services.base_service import BaseService
from app.models import User
from app.utils.security import get_password_hash, verify_password


class UserService(BaseService):
    """Service for managing users"""
    
    COLLECTION = "users"
    
    async def create_user(
        self, 
        email: str, 
        username: str,
        password: str, 
        role: str = "operator",
        full_name: Optional[str] = None
    ) -> User:
        """
        Create a new user
        
        Args:
            email: User email
            username: Username
            password: Plain text password
            role: User role (admin, operator, viewer)
            full_name: Optional full name
            
        Returns:
            Created user
            
        Raises:
            ValueError: If user already exists
            RuntimeError: If database operation fails
        """
        try:
            # Hash password
            hashed_password = get_password_hash(password)
            
            # Create user document
            user_dict = {
                "email": email,
                "username": username,
                "hashed_password": hashed_password,
                "full_name": full_name,
                "role": role,
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            # Insert into database
            result = await self.db[self.COLLECTION].insert_one(user_dict)
            user_dict["_id"] = result.inserted_id
            
            self.logger.info(f"Created user: {username} ({email})")
            return User(**user_dict)
            
        except DuplicateKeyError:
            self.logger.warning(f"User already exists: {email}")
            raise ValueError(f"User with email {email} already exists")
        except PyMongoError as e:
            self.logger.error(f"Database error creating user: {e}")
            raise RuntimeError(f"Failed to create user: {str(e)}")
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """
        Get user by ID
        
        Args:
            user_id: User ID
            
        Returns:
            User if found, None otherwise
        """
        try:
            if not ObjectId.is_valid(user_id):
                return None
            
            user_dict = await self.db[self.COLLECTION].find_one({"_id": ObjectId(user_id)})
            if user_dict:
                return User(**user_dict)
            return None
            
        except PyMongoError as e:
            self.logger.error(f"Database error fetching user {user_id}: {e}")
            return None
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email
        
        Args:
            email: User email
            
        Returns:
            User if found, None otherwise
        """
        try:
            user_dict = await self.db[self.COLLECTION].find_one({"email": email})
            if user_dict:
                return User(**user_dict)
            return None
            
        except PyMongoError as e:
            self.logger.error(f"Database error fetching user by email {email}: {e}")
            return None
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Get user by username
        
        Args:
            username: Username
            
        Returns:
            User if found, None otherwise
        """
        try:
            user_dict = await self.db[self.COLLECTION].find_one({"username": username})
            if user_dict:
                return User(**user_dict)
            return None
            
        except PyMongoError as e:
            self.logger.error(f"Database error fetching user by username {username}: {e}")
            return None
    
    async def update_user(self, user_id: str, updates: dict) -> Optional[User]:
        """
        Update user
        
        Args:
            user_id: User ID
            updates: Dictionary of fields to update
            
        Returns:
            Updated user if found, None otherwise
        """
        try:
            if not ObjectId.is_valid(user_id):
                return None
            
            # Add updated_at timestamp
            updates["updated_at"] = datetime.utcnow()
            
            # Update user
            result = await self.db[self.COLLECTION].find_one_and_update(
                {"_id": ObjectId(user_id)},
                {"$set": updates},
                return_document=True
            )
            
            if result:
                self.logger.info(f"Updated user: {user_id}")
                return User(**result)
            return None
            
        except PyMongoError as e:
            self.logger.error(f"Database error updating user {user_id}: {e}")
            return None
    
    async def delete_user(self, user_id: str) -> bool:
        """
        Delete user
        
        Args:
            user_id: User ID
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            if not ObjectId.is_valid(user_id):
                return False
            
            result = await self.db[self.COLLECTION].delete_one({"_id": ObjectId(user_id)})
            
            if result.deleted_count > 0:
                self.logger.info(f"Deleted user: {user_id}")
                return True
            return False
            
        except PyMongoError as e:
            self.logger.error(f"Database error deleting user {user_id}: {e}")
            return False
    
    async def list_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """
        List users with pagination
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of users
        """
        try:
            cursor = self.db[self.COLLECTION].find().skip(skip).limit(limit)
            users = []
            async for user_dict in cursor:
                users.append(User(**user_dict))
            return users
            
        except PyMongoError as e:
            self.logger.error(f"Database error listing users: {e}")
            return []
    
    def verify_password(self, user: User, password: str) -> bool:
        """
        Verify user password
        
        Args:
            user: User object
            password: Plain text password to verify
            
        Returns:
            True if password is correct, False otherwise
        """
        return verify_password(password, user.hashed_password)
    
    async def ensure_indexes(self):
        """Create necessary indexes for users collection"""
        try:
            await self.db[self.COLLECTION].create_index("email", unique=True)
            await self.db[self.COLLECTION].create_index("username", unique=True)
            self.logger.info("User indexes created")
        except PyMongoError as e:
            self.logger.error(f"Error creating user indexes: {e}")
