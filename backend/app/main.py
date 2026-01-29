"""Main FastAPI application"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import socketio

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


# Create Socket.IO server
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=False,
    engineio_logger=False
)

# Store active run subscriptions: {sid: set(run_ids)}
run_subscriptions = {}


@sio.event
async def connect(sid, environ, auth):
    """Handle client connection"""
    logger.info(f"Socket.IO client connected: {sid}")
    run_subscriptions[sid] = set()
    return True


@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    logger.info(f"Socket.IO client disconnected: {sid}")
    if sid in run_subscriptions:
        del run_subscriptions[sid]


@sio.event
async def subscribe_run(sid, data):
    """Subscribe to run updates"""
    run_id = data.get('run_id')
    if run_id:
        run_subscriptions.setdefault(sid, set()).add(run_id)
        logger.debug(f"Client {sid} subscribed to run {run_id}")
        await sio.emit('subscribed', {'run_id': run_id}, room=sid)


@sio.event
async def unsubscribe_run(sid, data):
    """Unsubscribe from run updates"""
    run_id = data.get('run_id')
    if run_id and sid in run_subscriptions:
        run_subscriptions[sid].discard(run_id)
        logger.debug(f"Client {sid} unsubscribed from run {run_id}")
        await sio.emit('unsubscribed', {'run_id': run_id}, room=sid)


async def broadcast_run_update(run_id: str, data: dict):
    """
    Broadcast run update to all subscribed clients
    
    Args:
        run_id: Run ID
        data: Update data to broadcast
    """
    for sid, subscribed_runs in run_subscriptions.items():
        if run_id in subscribed_runs:
            await sio.emit('run_update', data, room=sid)


# Wrap FastAPI app with Socket.IO
socket_app = socketio.ASGIApp(sio, app)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(socket_app, host="0.0.0.0", port=8000)
