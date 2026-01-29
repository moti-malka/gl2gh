"""Base service class for database operations"""

from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db import get_database
from app.utils.logging import get_logger


class BaseService:
    """Base service class with database connection"""
    
    def __init__(self, db: Optional[AsyncIOMotorDatabase] = None):
        """
        Initialize base service
        
        Args:
            db: Optional database instance. If not provided, will use get_database()
        """
        self._db = db
        self.logger = get_logger(self.__class__.__name__)
    
    @property
    def db(self) -> AsyncIOMotorDatabase:
        """Get database instance"""
        if self._db is None:
            self._db = get_database()
        return self._db
