"""Main FastAPI application"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.db import connect_to_mongo, close_mongo_connection
from app.utils.logging import setup_logging, get_logger
from app.api import auth, projects, connections, runs, events

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events"""
    # Startup
    setup_logging()
    logger.info("Starting gl2gh Migration Platform")
    await connect_to_mongo()
    yield
    # Shutdown
    logger.info("Shutting down gl2gh Migration Platform")
    await close_mongo_connection()


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["auth"])
app.include_router(projects.router, prefix=f"{settings.API_V1_PREFIX}/projects", tags=["projects"])
app.include_router(connections.router, prefix=f"{settings.API_V1_PREFIX}/projects", tags=["connections"])
app.include_router(runs.router, prefix=f"{settings.API_V1_PREFIX}", tags=["runs"])
app.include_router(events.router, prefix=f"{settings.API_V1_PREFIX}/runs", tags=["events"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
