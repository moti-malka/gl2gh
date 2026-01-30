"""
SSE (Server-Sent Events) manager for broadcasting run updates

This module manages SSE connections and broadcasts events to subscribed clients.
"""

import asyncio
from typing import Dict, Set
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class SSEManager:
    """Manages Server-Sent Events connections and broadcasts"""
    
    def __init__(self):
        # Map of run_id -> set of queues for subscribed clients
        self._subscriptions: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        self._lock = asyncio.Lock()
    
    async def subscribe(self, run_id: str) -> asyncio.Queue:
        """
        Subscribe to updates for a specific run
        
        Args:
            run_id: Run ID to subscribe to
            
        Returns:
            Queue that will receive updates for this run
        """
        queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subscriptions[run_id].add(queue)
            logger.debug(f"Client subscribed to run {run_id}. Total subscribers: {len(self._subscriptions[run_id])}")
        return queue
    
    async def unsubscribe(self, run_id: str, queue: asyncio.Queue):
        """
        Unsubscribe from run updates
        
        Args:
            run_id: Run ID to unsubscribe from
            queue: Queue to remove from subscriptions
        """
        async with self._lock:
            if run_id in self._subscriptions:
                self._subscriptions[run_id].discard(queue)
                logger.debug(f"Client unsubscribed from run {run_id}. Remaining subscribers: {len(self._subscriptions[run_id])}")
                
                # Clean up empty subscription sets
                if not self._subscriptions[run_id]:
                    del self._subscriptions[run_id]
    
    async def broadcast(self, run_id: str, data: dict):
        """
        Broadcast an update to all subscribers of a run
        
        Args:
            run_id: Run ID to broadcast to
            data: Data to broadcast
        """
        async with self._lock:
            subscribers = self._subscriptions.get(run_id, set()).copy()
        
        if not subscribers:
            logger.debug(f"No SSE subscribers for run {run_id}")
            return
        
        logger.debug(f"Broadcasting to {len(subscribers)} SSE subscribers for run {run_id}")
        
        for queue in subscribers:
            try:
                # Use put_nowait to avoid blocking
                # If queue is full, skip this update for this client
                if queue.full():
                    logger.warning(f"SSE queue full for run {run_id}, skipping update")
                else:
                    queue.put_nowait(data)
            except asyncio.QueueFull:
                logger.warning(f"Failed to queue SSE update for run {run_id}")
            except Exception as e:
                logger.error(f"Error broadcasting SSE update for run {run_id}: {e}")
    
    def get_subscriber_count(self, run_id: str) -> int:
        """Get the number of subscribers for a run"""
        return len(self._subscriptions.get(run_id, set()))


# Global SSE manager instance
sse_manager = SSEManager()
