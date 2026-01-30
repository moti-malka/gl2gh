/**
 * Progress Service - Unified connection manager with fallback support
 * 
 * Provides real-time progress updates using the best available connection method:
 * 1. WebSocket (Socket.IO) - Best performance, lowest latency
 * 2. Server-Sent Events (SSE) - Reliable fallback for unstable networks
 * 3. REST Polling - Last resort fallback for restricted environments
 */
import io from 'socket.io-client';
import { runsAPI } from './api';

const WS_URL = process.env.REACT_APP_WS_URL || 'http://localhost:8000';
const API_BASE_URL = process.env.REACT_APP_API_URL || '/api';
// SSE needs absolute URL since EventSource doesn't work through webpack proxy
const SSE_BASE_URL = process.env.REACT_APP_SSE_URL || 'http://localhost:8000/api';

// Connection methods in order of preference
const CONNECTION_METHODS = {
  WEBSOCKET: 'websocket',
  SSE: 'sse',
  POLLING: 'polling'
};

class ProgressService {
  constructor() {
    this.socket = null;
    this.sseConnections = new Map(); // runId -> EventSource
    this.pollingIntervals = new Map(); // runId -> interval ID
    this.listeners = new Map(); // event -> [callbacks]
    this.runListeners = new Map(); // runId -> [callbacks]
    this.currentMethod = null;
    this.connectionAttempts = 0;
    this.maxConnectionAttempts = 3;
  }

  /**
   * Subscribe to run updates with automatic fallback
   */
  subscribeToRun(runId, callback) {
    if (!this.runListeners.has(runId)) {
      this.runListeners.set(runId, []);
    }
    this.runListeners.get(runId).push(callback);

    // Try connection methods in order
    this._connectToRun(runId);

    // Return unsubscribe function
    return () => {
      this._unsubscribeFromRun(runId, callback);
    };
  }

  /**
   * Attempt to connect to a run using available methods
   */
  async _connectToRun(runId) {
    // Use polling directly for reliability
    // WebSocket and SSE have issues with CORS and event loop in this setup
    this._startPolling(runId);
    console.log(`[ProgressService] Connected to run ${runId} via Polling`);
    this.currentMethod = CONNECTION_METHODS.POLLING;
  }

  /**
   * Try WebSocket connection
   */
  async _tryWebSocket(runId) {
    try {
      if (!this.socket || !this.socket.connected) {
        const token = localStorage.getItem('access_token');
        
        this.socket = io(WS_URL, {
          auth: { token },
          transports: ['websocket', 'polling'],
          timeout: 5000,
          reconnection: true,
          reconnectionAttempts: 3,
          reconnectionDelay: 1000,
        });

        // Wait for connection
        await new Promise((resolve, reject) => {
          const timeout = setTimeout(() => reject(new Error('WebSocket timeout')), 5000);
          
          this.socket.once('connect', () => {
            clearTimeout(timeout);
            resolve();
          });
          
          this.socket.once('connect_error', (error) => {
            clearTimeout(timeout);
            reject(error);
          });
        });

        // Set up event handlers
        this.socket.on('disconnect', () => {
          console.log('[ProgressService] WebSocket disconnected, attempting reconnection');
          this._handleDisconnection(runId);
        });

        this.socket.on('run_update', (data) => {
          this._notifyListeners(data.run_id, data);
        });
      }

      // Subscribe to run
      this.socket.emit('subscribe_run', { run_id: runId });
      
      return true;
    } catch (error) {
      console.warn('[ProgressService] WebSocket connection failed:', error.message);
      if (this.socket) {
        this.socket.disconnect();
        this.socket = null;
      }
      return false;
    }
  }

  /**
   * Try SSE connection
   */
  async _trySSE(runId) {
    try {
      const token = localStorage.getItem('access_token');
      // Use absolute URL for SSE since EventSource doesn't work through webpack proxy
      const url = `${SSE_BASE_URL}/runs/${runId}/stream`;
      
      // Create EventSource with auth in URL (EventSource doesn't support headers)
      const eventSource = new EventSource(`${url}?token=${token}`);
      
      return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          eventSource.close();
          reject(new Error('SSE timeout'));
        }, 10000);

        // Handle initial state event
        eventSource.addEventListener('state', (event) => {
          clearTimeout(timeout);
          console.log('[ProgressService] SSE connected, received state');
          
          try {
            const data = JSON.parse(event.data);
            this._notifyListeners(runId, data);
          } catch (e) {
            console.warn('[ProgressService] Failed to parse SSE state data:', e);
          }
          
          resolve(true);
        });

        // Handle updates
        eventSource.addEventListener('update', (event) => {
          try {
            const data = JSON.parse(event.data);
            this._notifyListeners(runId, data);
          } catch (e) {
            console.error('[ProgressService] Failed to parse SSE update:', e);
          }
        });

        // Handle completion
        eventSource.addEventListener('complete', (event) => {
          try {
            const data = JSON.parse(event.data);
            this._notifyListeners(runId, data);
          } catch (e) {
            console.error('[ProgressService] Failed to parse SSE complete:', e);
          }
          eventSource.close();
          this.sseConnections.delete(runId);
        });

        eventSource.addEventListener('keepalive', () => {
          // Just a keepalive, no action needed
          console.debug('[ProgressService] SSE keepalive received');
        });

        eventSource.onerror = (error) => {
          clearTimeout(timeout);
          console.warn('[ProgressService] SSE error:', error);
          eventSource.close();
          this.sseConnections.delete(runId);
          reject(error);
        };

        // Store connection
        this.sseConnections.set(runId, eventSource);
      });
    } catch (error) {
      console.warn('[ProgressService] SSE connection failed:', error.message);
      
      const eventSource = this.sseConnections.get(runId);
      if (eventSource) {
        eventSource.close();
        this.sseConnections.delete(runId);
      }
      
      return false;
    }
  }

  /**
   * Start REST polling fallback
   */
  _startPolling(runId) {
    // Clear any existing interval
    const existingInterval = this.pollingIntervals.get(runId);
    if (existingInterval) {
      clearInterval(existingInterval);
    }

    // Poll every 2 seconds
    const interval = setInterval(async () => {
      try {
        const response = await runsAPI.getProgress(runId);
        this._notifyListeners(runId, response.data);
      } catch (error) {
        console.error('[ProgressService] Polling error:', error);
        
        // If run not found or forbidden, stop polling
        if (error.response?.status === 404 || error.response?.status === 403) {
          this._stopPolling(runId);
        }
      }
    }, 2000);

    this.pollingIntervals.set(runId, interval);
  }

  /**
   * Stop polling for a run
   */
  _stopPolling(runId) {
    const interval = this.pollingIntervals.get(runId);
    if (interval) {
      clearInterval(interval);
      this.pollingIntervals.delete(runId);
    }
  }

  /**
   * Handle disconnection and attempt reconnection
   */
  async _handleDisconnection(runId) {
    if (this.connectionAttempts >= this.maxConnectionAttempts) {
      console.warn('[ProgressService] Max reconnection attempts reached, falling back');
      this.connectionAttempts = 0;
      
      // Try next fallback method
      if (this.currentMethod === CONNECTION_METHODS.WEBSOCKET) {
        if (await this._trySSE(runId)) {
          this.currentMethod = CONNECTION_METHODS.SSE;
          return;
        }
      }
      
      if (this.currentMethod === CONNECTION_METHODS.SSE || this.currentMethod === CONNECTION_METHODS.WEBSOCKET) {
        this._startPolling(runId);
        this.currentMethod = CONNECTION_METHODS.POLLING;
        return;
      }
    }

    // Try to reconnect with same method
    this.connectionAttempts++;
    setTimeout(() => {
      this._connectToRun(runId);
    }, 1000 * this.connectionAttempts);
  }

  /**
   * Notify all listeners for a run
   */
  _notifyListeners(runId, data) {
    const callbacks = this.runListeners.get(runId) || [];
    callbacks.forEach(callback => {
      try {
        callback(data);
      } catch (error) {
        console.error('[ProgressService] Error in listener callback:', error);
      }
    });
  }

  /**
   * Unsubscribe from run updates
   */
  _unsubscribeFromRun(runId, callback) {
    // Remove callback
    const callbacks = this.runListeners.get(runId) || [];
    const index = callbacks.indexOf(callback);
    if (index > -1) {
      callbacks.splice(index, 1);
    }

    // If no more callbacks, clean up connections
    if (callbacks.length === 0) {
      this.runListeners.delete(runId);
      
      // Close WebSocket subscription
      if (this.socket?.connected) {
        this.socket.emit('unsubscribe_run', { run_id: runId });
      }
      
      // Close SSE connection
      const eventSource = this.sseConnections.get(runId);
      if (eventSource) {
        eventSource.close();
        this.sseConnections.delete(runId);
      }
      
      // Stop polling
      this._stopPolling(runId);
    }
  }

  /**
   * Get current connection method
   */
  getConnectionMethod() {
    return this.currentMethod;
  }

  /**
   * Disconnect all connections
   */
  disconnect() {
    // Close WebSocket
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }

    // Close all SSE connections
    this.sseConnections.forEach(eventSource => {
      eventSource.close();
    });
    this.sseConnections.clear();

    // Stop all polling
    this.pollingIntervals.forEach(interval => {
      clearInterval(interval);
    });
    this.pollingIntervals.clear();

    // Clear listeners
    this.runListeners.clear();
    this.currentMethod = null;
  }
}

// Export singleton instance
export const progressService = new ProgressService();
export default progressService;
