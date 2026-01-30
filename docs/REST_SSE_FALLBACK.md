# REST/SSE Fallback for Progress Updates

## Overview

This implementation adds robust fallback mechanisms for real-time progress updates, ensuring users can receive updates even when WebSocket connections are unreliable or unavailable.

## Backend Implementation

### New Endpoints

#### 1. REST Polling Endpoint
```
GET /api/v1/runs/{run_id}/progress
```
- **Purpose**: Provides current run progress for polling clients
- **Returns**: Current run status, stage, progress details, and statistics
- **Use Case**: Last-resort fallback for restricted environments

#### 2. Server-Sent Events (SSE) Endpoint
```
GET /api/v1/runs/{run_id}/stream
```
- **Purpose**: Real-time event stream using SSE protocol
- **Returns**: Stream of run updates and keepalive events
- **Use Case**: Reliable alternative to WebSocket for unstable networks

### Architecture Changes

#### SSE Manager (`app/utils/sse_manager.py`)
- Manages SSE subscriptions per run
- Broadcasts updates to all subscribed SSE clients
- Handles automatic cleanup of closed connections

#### Enhanced Broadcasting (`app/utils/websocket.py`)
- Updated to broadcast to both WebSocket AND SSE subscribers
- Ensures all connection types receive updates simultaneously

#### Extended Run Model (`app/models/__init__.py`)
- Added `current_stage` field for detailed stage tracking
- Added `progress` dict for granular progress information (percentage, messages, etc.)

#### RunService Updates (`app/services/run_service.py`)
- New `update_run_progress()` method for updating progress details
- Supports partial updates (current_stage or progress independently)

## Frontend Implementation

### Progress Service (`frontend/src/services/progress.js`)

The new `ProgressService` automatically manages connections with fallback:

#### Connection Priority
1. **WebSocket (Socket.IO)** - Best performance, lowest latency
2. **Server-Sent Events (SSE)** - Reliable for unstable networks
3. **REST Polling** - Last resort for restricted environments

#### Features
- **Automatic Fallback**: Tries each method in order until successful
- **Reconnection Handling**: Automatically attempts reconnection on disconnect
- **Seamless Switching**: Transparently switches between methods without user action
- **Connection Indicator**: Visual feedback showing current connection method

### Usage Example

```javascript
import { progressService } from './services/progress';

// Subscribe to run updates
const unsubscribe = progressService.subscribeToRun(runId, (data) => {
  console.log('Progress update:', data);
  // Update UI with new data
});

// Get current connection method
const method = progressService.getConnectionMethod(); // 'websocket' | 'sse' | 'polling'

// Cleanup when done
unsubscribe();
```

### UI Integration

The `RunDashboardPage` now displays:
- **Connection Indicator**: Shows which method is currently active
  - 🔗 WebSocket (green) - Optimal connection
  - 📡 SSE (yellow) - Fallback connection
  - 🔄 Polling (red) - Last resort fallback
- Automatic reconnection on network issues
- No user intervention required

## Benefits

### Reliability
- Users always receive updates, regardless of network conditions
- Automatic fallback ensures continuous monitoring

### Performance
- Uses best available connection method
- Reduces server load with efficient broadcasting

### User Experience
- Transparent operation - users don't need to manage connections
- Visual feedback on connection status
- No missed updates during reconnection

## Testing

### Backend Tests (`backend/tests/test_progress_endpoints.py`)
- REST endpoint authentication and authorization
- SSE stream connection establishment
- SSE manager subscription/unsubscribe
- Broadcast to multiple subscribers
- RunService progress update methods

### Frontend Testing
Manual testing recommended for:
1. WebSocket connection and fallback to SSE
2. SSE fallback to polling
3. Reconnection after network interruption
4. Connection indicator updates

## Configuration

### Environment Variables
No new environment variables required. Uses existing:
- `REACT_APP_API_URL` - API base URL for REST and SSE
- `REACT_APP_WS_URL` - WebSocket server URL

### Server Configuration
SSE endpoints use standard FastAPI streaming:
- No special server configuration needed
- Works with standard ASGI servers (uvicorn, hypercorn)
- Compatible with reverse proxies (nginx, traefik)

## Migration Notes

### Backward Compatibility
- Old WebSocket-only clients continue to work
- No breaking changes to existing APIs
- New fields in MigrationRun model have defaults

### Database Migration
The new fields `current_stage` and `progress` are added to the `runs` collection:
- Existing runs will have `null` values (safe)
- New runs automatically include these fields
- No manual migration required

## Future Enhancements

Potential improvements:
1. **Missed Event Recovery**: Store recent events for reconnecting clients
2. **Progress Snapshots**: Periodic snapshots for quick reconnection
3. **Metrics**: Track connection method usage and fallback frequency
4. **Compression**: Compress SSE messages for bandwidth efficiency
