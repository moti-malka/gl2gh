#!/usr/bin/env python3
"""Initialize database with admin user"""

import asyncio
import sys
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import connect_to_mongo, close_mongo_connection
from app.services import UserService
from app.utils.logging import setup_logging, get_logger


async def create_admin_user():
    """Create initial admin user"""
    setup_logging()
    logger = get_logger(__name__)
    
    logger.info("Connecting to database...")
    await connect_to_mongo()
    
    try:
        user_service = UserService()
        
        # Create indexes
        await user_service.ensure_indexes()
        
        # Check if admin already exists
        existing_admin = await user_service.get_user_by_email("admin@gl2gh.local")
        if existing_admin:
            logger.info("Admin user already exists")
            return
        
        # Create admin user
        logger.info("Creating admin user...")
        admin = await user_service.create_user(
            email="admin@gl2gh.local",
            username="admin",
            password="admin123",  # Change in production!
            role="admin",
            full_name="System Administrator"
        )
        
        logger.info(f"Admin user created successfully: {admin.email}")
        logger.info("Default credentials: admin@gl2gh.local / admin123")
        logger.info("IMPORTANT: Change the default password immediately!")
        
    except Exception as e:
        logger.error(f"Error creating admin user: {e}")
        raise
    finally:
        await close_mongo_connection()


if __name__ == "__main__":
    asyncio.run(create_admin_user())
