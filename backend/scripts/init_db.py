#!/usr/bin/env python3
"""Initialize all database indexes"""

import asyncio
import sys
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import connect_to_mongo, close_mongo_connection
from app.services import (
    UserService,
    ProjectService,
    ConnectionService,
    RunService,
    EventService,
    ArtifactService,
    UserMappingService
)
from app.utils.logging import setup_logging, get_logger


async def init_indexes():
    """Initialize all database indexes"""
    setup_logging()
    logger = get_logger(__name__)
    
    logger.info("Connecting to database...")
    await connect_to_mongo()
    
    try:
        # Create indexes for all services
        services = [
            ("Users", UserService()),
            ("Projects", ProjectService()),
            ("Connections", ConnectionService()),
            ("Runs", RunService()),
            ("Events", EventService()),
            ("Artifacts", ArtifactService()),
            ("User Mappings", UserMappingService())
        ]
        
        for name, service in services:
            logger.info(f"Creating indexes for {name}...")
            await service.ensure_indexes()
        
        logger.info("All indexes created successfully!")
        
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")
        raise
    finally:
        await close_mongo_connection()


if __name__ == "__main__":
    asyncio.run(init_indexes())
