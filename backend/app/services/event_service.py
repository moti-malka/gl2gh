"""Event service for managing migration run events"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
from pymongo.errors import PyMongoError

from app.services.base_service import BaseService
from app.models import Event


class EventService(BaseService):
    """Service for managing migration run events"""
    
    COLLECTION = "events"
    
    async def create_event(
        self,
        run_id: str,
        level: str,
        message: str,
        agent: Optional[str] = None,
        scope: str = "run",
        gitlab_project_id: Optional[int] = None,
        payload: Optional[Dict[str, Any]] = None
    ) -> Event:
        """
        Create a new event
        
        Args:
            run_id: Run ID
            level: Event level (INFO, WARN, ERROR, DEBUG)
            message: Event message
            agent: Optional agent name (DiscoveryAgent, ExportAgent, etc.)
            scope: Event scope (run or project)
            gitlab_project_id: Optional GitLab project ID for project-scoped events
            payload: Optional additional data
            
        Returns:
            Created event
            
        Raises:
            ValueError: If run_id is not valid
            RuntimeError: If database operation fails
        """
        try:
            if not ObjectId.is_valid(run_id):
                raise ValueError(f"Invalid run ID: {run_id}")
            
            # Create event document
            event_dict = {
                "run_id": ObjectId(run_id),
                "timestamp": datetime.utcnow(),
                "level": level,
                "agent": agent,
                "scope": scope,
                "gitlab_project_id": gitlab_project_id,
                "message": message,
                "payload": payload or {}
            }
            
            # Insert into database
            result = await self.db[self.COLLECTION].insert_one(event_dict)
            event_dict["_id"] = result.inserted_id
            
            self.logger.debug(f"Created {level} event for run {run_id}: {message}")
            return Event(**event_dict)
            
        except PyMongoError as e:
            self.logger.error(f"Database error creating event: {e}")
            raise RuntimeError(f"Failed to create event: {str(e)}")
    
    async def get_events(
        self,
        run_id: str,
        skip: int = 0,
        limit: int = 100,
        level_filter: Optional[str] = None,
        agent_filter: Optional[str] = None,
        scope_filter: Optional[str] = None
    ) -> List[Event]:
        """
        Get events for a run with pagination and filtering
        
        Args:
            run_id: Run ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            level_filter: Optional filter by level
            agent_filter: Optional filter by agent
            scope_filter: Optional filter by scope
            
        Returns:
            List of events
        """
        try:
            if not ObjectId.is_valid(run_id):
                return []
            
            # Build query
            query = {"run_id": ObjectId(run_id)}
            
            if level_filter:
                query["level"] = level_filter
            
            if agent_filter:
                query["agent"] = agent_filter
            
            if scope_filter:
                query["scope"] = scope_filter
            
            # Fetch events (sorted by timestamp descending)
            cursor = self.db[self.COLLECTION].find(query).skip(skip).limit(limit).sort("timestamp", -1)
            events = []
            async for event_dict in cursor:
                events.append(Event(**event_dict))
            return events
            
        except PyMongoError as e:
            self.logger.error(f"Database error fetching events for run {run_id}: {e}")
            return []
    
    async def get_events_by_agent(self, run_id: str, agent: str) -> List[Event]:
        """
        Get all events for a specific agent
        
        Args:
            run_id: Run ID
            agent: Agent name
            
        Returns:
            List of events
        """
        return await self.get_events(run_id, agent_filter=agent, limit=1000)
    
    async def get_error_events(self, run_id: str, limit: int = 100) -> List[Event]:
        """
        Get error events for a run
        
        Args:
            run_id: Run ID
            limit: Maximum number of records to return
            
        Returns:
            List of error events
        """
        return await self.get_events(run_id, level_filter="ERROR", limit=limit)
    
    async def count_events(
        self,
        run_id: str,
        level_filter: Optional[str] = None,
        agent_filter: Optional[str] = None
    ) -> int:
        """
        Count events for a run
        
        Args:
            run_id: Run ID
            level_filter: Optional filter by level
            agent_filter: Optional filter by agent
            
        Returns:
            Number of events
        """
        try:
            if not ObjectId.is_valid(run_id):
                return 0
            
            query = {"run_id": ObjectId(run_id)}
            
            if level_filter:
                query["level"] = level_filter
            
            if agent_filter:
                query["agent"] = agent_filter
            
            count = await self.db[self.COLLECTION].count_documents(query)
            return count
            
        except PyMongoError as e:
            self.logger.error(f"Database error counting events for run {run_id}: {e}")
            return 0
    
    async def delete_run_events(self, run_id: str) -> int:
        """
        Delete all events for a run
        
        Args:
            run_id: Run ID
            
        Returns:
            Number of events deleted
        """
        try:
            if not ObjectId.is_valid(run_id):
                return 0
            
            result = await self.db[self.COLLECTION].delete_many({"run_id": ObjectId(run_id)})
            count = result.deleted_count
            
            if count > 0:
                self.logger.info(f"Deleted {count} events for run {run_id}")
            return count
            
        except PyMongoError as e:
            self.logger.error(f"Database error deleting events for run {run_id}: {e}")
            return 0
    
    async def ensure_indexes(self):
        """Create necessary indexes for events collection"""
        try:
            await self.db[self.COLLECTION].create_index("run_id")
            await self.db[self.COLLECTION].create_index([("run_id", 1), ("timestamp", -1)])
            await self.db[self.COLLECTION].create_index([("run_id", 1), ("level", 1)])
            await self.db[self.COLLECTION].create_index([("run_id", 1), ("agent", 1)])
            self.logger.info("Event indexes created")
        except PyMongoError as e:
            self.logger.error(f"Error creating event indexes: {e}")
