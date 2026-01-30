"""Tests for REST and SSE fallback endpoints"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from bson import ObjectId

from app.models import MigrationRun, RunStats
from app.utils.sse_manager import sse_manager


class TestRunProgressEndpoint:
    """Tests for the /runs/{run_id}/progress REST endpoint"""
    
    @pytest.mark.asyncio
    async def test_get_run_progress_success(self, test_client, mock_current_user, mock_run):
        """Test successful progress retrieval"""
        # Mock the run service
        with test_client:
            response = await test_client.get(
                f"/api/v1/runs/{str(mock_run.id)}/progress",
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == str(mock_run.id)
        assert "status" in data
        assert "stage" in data
        assert "current_stage" in data
        assert "progress" in data
        assert "stats" in data
    
    @pytest.mark.asyncio
    async def test_get_run_progress_not_found(self, test_client, mock_current_user):
        """Test progress retrieval for non-existent run"""
        fake_id = str(ObjectId())
        
        with test_client:
            response = await test_client.get(
                f"/api/v1/runs/{fake_id}/progress",
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_get_run_progress_unauthorized(self, test_client):
        """Test progress retrieval without authentication"""
        fake_id = str(ObjectId())
        
        with test_client:
            response = await test_client.get(f"/api/v1/runs/{fake_id}/progress")
        
        assert response.status_code == 401


class TestRunEventsStreamEndpoint:
    """Tests for the /runs/{run_id}/stream SSE endpoint"""
    
    @pytest.mark.asyncio
    async def test_sse_stream_connection(self, test_client, mock_current_user, mock_run):
        """Test SSE stream connection establishment"""
        # This is a basic test since testing SSE streams is complex
        # We verify the endpoint exists and requires auth
        with test_client:
            response = await test_client.get(
                f"/api/v1/runs/{str(mock_run.id)}/stream",
                headers={"Authorization": "Bearer test_token"}
            )
        
        # SSE endpoints typically return 200 and stream content
        # The response will be streaming, so we just check it starts correctly
        assert response.status_code in [200, 307]  # 307 for redirects in test mode
    
    @pytest.mark.asyncio
    async def test_sse_stream_unauthorized(self, test_client):
        """Test SSE stream without authentication"""
        fake_id = str(ObjectId())
        
        with test_client:
            response = await test_client.get(f"/api/v1/runs/{fake_id}/stream")
        
        assert response.status_code == 401


class TestSSEManager:
    """Tests for the SSE manager"""
    
    @pytest.mark.asyncio
    async def test_subscribe_and_unsubscribe(self):
        """Test subscribing and unsubscribing from run updates"""
        run_id = str(ObjectId())
        
        # Subscribe
        queue = await sse_manager.subscribe(run_id)
        assert queue is not None
        assert sse_manager.get_subscriber_count(run_id) == 1
        
        # Unsubscribe
        await sse_manager.unsubscribe(run_id, queue)
        assert sse_manager.get_subscriber_count(run_id) == 0
    
    @pytest.mark.asyncio
    async def test_broadcast_to_subscribers(self):
        """Test broadcasting updates to subscribers"""
        run_id = str(ObjectId())
        
        # Subscribe
        queue = await sse_manager.subscribe(run_id)
        
        # Broadcast update
        test_data = {"status": "RUNNING", "stage": "DISCOVERY"}
        await sse_manager.broadcast(run_id, test_data)
        
        # Check if update was received
        update = await queue.get()
        assert update == test_data
        
        # Clean up
        await sse_manager.unsubscribe(run_id, queue)
    
    @pytest.mark.asyncio
    async def test_broadcast_with_no_subscribers(self):
        """Test broadcasting when there are no subscribers"""
        run_id = str(ObjectId())
        test_data = {"status": "RUNNING"}
        
        # Should not raise an error
        await sse_manager.broadcast(run_id, test_data)
        assert sse_manager.get_subscriber_count(run_id) == 0
    
    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        """Test multiple subscribers to the same run"""
        run_id = str(ObjectId())
        
        # Subscribe with multiple clients
        queue1 = await sse_manager.subscribe(run_id)
        queue2 = await sse_manager.subscribe(run_id)
        
        assert sse_manager.get_subscriber_count(run_id) == 2
        
        # Broadcast
        test_data = {"status": "COMPLETED"}
        await sse_manager.broadcast(run_id, test_data)
        
        # Both should receive the update
        update1 = await queue1.get()
        update2 = await queue2.get()
        
        assert update1 == test_data
        assert update2 == test_data
        
        # Clean up
        await sse_manager.unsubscribe(run_id, queue1)
        await sse_manager.unsubscribe(run_id, queue2)


class TestRunServiceProgress:
    """Tests for run service progress methods"""
    
    @pytest.mark.asyncio
    async def test_update_run_progress(self, run_service, mock_run):
        """Test updating run progress"""
        run_id = str(mock_run.id)
        
        # Update progress
        progress = {"percentage": 50, "message": "Processing projects"}
        updated_run = await run_service.update_run_progress(
            run_id=run_id,
            current_stage="Discovering projects",
            progress=progress
        )
        
        assert updated_run is not None
        assert updated_run.current_stage == "Discovering projects"
        assert updated_run.progress == progress
    
    @pytest.mark.asyncio
    async def test_update_run_progress_invalid_id(self, run_service):
        """Test updating progress with invalid run ID"""
        result = await run_service.update_run_progress(
            run_id="invalid_id",
            progress={"percentage": 50}
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_update_run_progress_partial(self, run_service, mock_run):
        """Test updating only current_stage or only progress"""
        run_id = str(mock_run.id)
        
        # Update only current_stage
        updated_run = await run_service.update_run_progress(
            run_id=run_id,
            current_stage="Exporting data"
        )
        
        assert updated_run is not None
        assert updated_run.current_stage == "Exporting data"
        
        # Update only progress
        updated_run = await run_service.update_run_progress(
            run_id=run_id,
            progress={"percentage": 75}
        )
        
        assert updated_run is not None
        assert updated_run.progress == {"percentage": 75}


@pytest.fixture
def mock_run():
    """Create a mock migration run"""
    return MigrationRun(
        _id=ObjectId(),
        project_id=ObjectId(),
        mode="PLAN_ONLY",
        status="RUNNING",
        stage="DISCOVERY",
        current_stage="Fetching projects",
        progress={"percentage": 25, "projects_processed": 5},
        started_at=datetime.utcnow(),
        stats=RunStats(projects=5, groups=2),
        config_snapshot={}
    )


@pytest.fixture
def run_service():
    """Create a run service instance"""
    from app.services import RunService
    return RunService()
