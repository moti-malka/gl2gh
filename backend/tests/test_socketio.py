"""Tests for Socket.IO WebSocket functionality"""

import pytest
from app.main import socket_app, sio, run_subscriptions, broadcast_run_update
import asyncio


@pytest.mark.asyncio
async def test_socketio_server_configured():
    """Test that Socket.IO server is properly configured"""
    assert sio is not None
    assert socket_app is not None
    assert sio.async_mode == 'asgi'
    

@pytest.mark.asyncio
async def test_run_subscriptions_structure():
    """Test that run_subscriptions dictionary exists"""
    assert isinstance(run_subscriptions, dict)


@pytest.mark.asyncio
async def test_broadcast_run_update_function_exists():
    """Test that broadcast_run_update function exists and is callable"""
    assert callable(broadcast_run_update)
    
    # Test calling broadcast with empty subscriptions (should not raise)
    test_run_id = "507f1f77bcf86cd799439011"
    test_update = {
        'run_id': test_run_id,
        'status': 'RUNNING',
        'stage': 'DISCOVERY',
    }
    
    try:
        await broadcast_run_update(test_run_id, test_update)
    except Exception as e:
        pytest.fail(f"broadcast_run_update raised exception: {e}")


@pytest.mark.asyncio
async def test_socketio_event_handlers_registered():
    """Test that Socket.IO event handlers are registered"""
    # Get registered event handlers
    handlers = sio.handlers.get('/', {})
    
    # Check that our custom events are registered
    assert 'connect' in handlers
    assert 'disconnect' in handlers
    assert 'subscribe_run' in handlers
    assert 'unsubscribe_run' in handlers

