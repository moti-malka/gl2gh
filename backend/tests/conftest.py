"""Test configuration and fixtures"""

import pytest
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os

# Set test environment variables
os.environ["MONGO_URL"] = os.getenv("MONGO_URL", "mongodb://localhost:27017")
os.environ["MONGO_DB_NAME"] = "gl2gh_test"
os.environ["APP_MASTER_KEY"] = "test-master-key-for-encryption-32bytes"
os.environ["SECRET_KEY"] = "test-secret-key-for-jwt"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db():
    """Provide test database instance"""
    from app.config import settings
    
    client = AsyncIOMotorClient(settings.MONGO_URL)
    database = client[settings.MONGO_DB_NAME]
    
    yield database
    
    # Cleanup: drop all collections
    collection_names = await database.list_collection_names()
    for collection in collection_names:
        await database[collection].drop()
    
    client.close()


@pytest.fixture
async def user_service(db):
    """Provide UserService instance"""
    from app.services import UserService
    return UserService(db)


@pytest.fixture
async def project_service(db):
    """Provide ProjectService instance"""
    from app.services import ProjectService
    return ProjectService(db)


@pytest.fixture
async def connection_service(db):
    """Provide ConnectionService instance"""
    from app.services import ConnectionService
    return ConnectionService(db)


@pytest.fixture
async def run_service(db):
    """Provide RunService instance"""
    from app.services import RunService
    return RunService(db)


@pytest.fixture
async def event_service(db):
    """Provide EventService instance"""
    from app.services import EventService
    return EventService(db)


@pytest.fixture
async def artifact_service(db):
    """Provide ArtifactService instance"""
    from app.services import ArtifactService
    return ArtifactService(db)


@pytest.fixture
async def user_mapping_service(db):
    """Provide UserMappingService instance"""
    from app.services import UserMappingService
    return UserMappingService(db)


@pytest.fixture
async def test_user(user_service):
    """Create a test user"""
    user = await user_service.create_user(
        email="test@example.com",
        username="testuser",
        password="testpass123",
        role="operator"
    )
    return user


@pytest.fixture
async def test_admin(user_service):
    """Create a test admin user"""
    admin = await user_service.create_user(
        email="admin@example.com",
        username="admin",
        password="adminpass123",
        role="admin"
    )
    return admin


@pytest.fixture
async def test_project(project_service, test_user):
    """Create a test project"""
    project = await project_service.create_project(
        name="Test Project",
        created_by=str(test_user.id),
        description="A test project"
    )
    return project
