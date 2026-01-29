"""Database connection and initialization"""

from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
from app.config import settings

# Global database client
_client: Optional[AsyncIOMotorClient] = None


async def connect_to_mongo():
    """Connect to MongoDB"""
    global _client
    _client = AsyncIOMotorClient(settings.MONGO_URL)
    
    # Ping the server to verify connection
    await _client.admin.command('ping')
    print(f"Connected to MongoDB at {settings.MONGO_URL}")


async def close_mongo_connection():
    """Close MongoDB connection"""
    global _client
    if _client:
        _client.close()
        print("Closed MongoDB connection")


def get_database():
    """Get database instance"""
    if _client is None:
        raise RuntimeError("Database not connected. Call connect_to_mongo() first.")
    return _client[settings.MONGO_DB_NAME]


def get_collection(name: str):
    """Get collection by name"""
    db = get_database()
    return db[name]
