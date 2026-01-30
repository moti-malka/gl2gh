"""
WebSocket utilities for broadcasting real-time updates

This module provides helper functions for broadcasting run updates
to connected WebSocket clients using the Socket.IO server and SSE connections.
"""

from typing import Dict, Any
import asyncio


async def emit_run_update(run_id: str, update_data: Dict[str, Any]):
    """
    Emit a run update to all subscribed clients (both WebSocket and SSE)
    
    This is a convenience function that can be called from services
    like RunService or EventService to broadcast updates.
    
    Args:
        run_id: The run ID to broadcast for
        update_data: The update data to send (should include run_id, status, stage, etc.)
    
    Example:
        ```python
        await emit_run_update(
            run_id="507f1f77bcf86cd799439011",
            update_data={
                "run_id": "507f1f77bcf86cd799439011",
                "status": "RUNNING",
                "stage": "DISCOVERY",
                "stats": {
                    "projects_discovered": 5,
                    "projects_exported": 0
                }
            }
        )
        ```
    """
    try:
        # Broadcast to WebSocket subscribers
        from app.main import broadcast_run_update
        await broadcast_run_update(run_id, update_data)
    except Exception as e:
        from app.utils.logging import get_logger
        logger = get_logger(__name__)
        logger.warning(f"Failed to broadcast WebSocket update for {run_id}: {e}")
    
    try:
        # Broadcast to SSE subscribers
        from app.utils.sse_manager import sse_manager
        await sse_manager.broadcast(run_id, update_data)
    except Exception as e:
        from app.utils.logging import get_logger
        logger = get_logger(__name__)
        logger.warning(f"Failed to broadcast SSE update for {run_id}: {e}")


def emit_run_update_sync(run_id: str, update_data: Dict[str, Any]):
    """
    Synchronous wrapper for emit_run_update
    
    This function can be called from synchronous code (like Celery tasks)
    to broadcast run updates. It creates a new event loop if needed.
    
    Args:
        run_id: The run ID to broadcast for
        update_data: The update data to send
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If already in an async context, schedule the task
            asyncio.create_task(emit_run_update(run_id, update_data))
        else:
            # Run in new event loop
            loop.run_until_complete(emit_run_update(run_id, update_data))
    except Exception as e:
        from app.utils.logging import get_logger
        logger = get_logger(__name__)
        logger.warning(f"Failed to emit run update sync for {run_id}: {e}")
