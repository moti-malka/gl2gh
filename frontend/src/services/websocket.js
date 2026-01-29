/**
 * WebSocket utility for real-time updates
 */
import io from 'socket.io-client';

const WS_URL = process.env.REACT_APP_WS_URL || 'http://localhost:8000';

class WebSocketService {
  constructor() {
    this.socket = null;
    this.listeners = new Map();
  }

  connect() {
    if (this.socket?.connected) {
      return;
    }

    const token = localStorage.getItem('access_token');
    
    this.socket = io(WS_URL, {
      auth: {
        token,
      },
      transports: ['websocket', 'polling'],
    });

    this.socket.on('connect', () => {
      console.log('WebSocket connected');
    });

    this.socket.on('disconnect', () => {
      console.log('WebSocket disconnected');
    });

    this.socket.on('error', (error) => {
      console.error('WebSocket error:', error);
    });

    // Forward events to listeners
    this.socket.onAny((event, ...args) => {
      const listeners = this.listeners.get(event) || [];
      listeners.forEach(callback => callback(...args));
    });
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
  }

  subscribe(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(callback);

    // Return unsubscribe function
    return () => {
      const listeners = this.listeners.get(event);
      if (listeners) {
        const index = listeners.indexOf(callback);
        if (index > -1) {
          listeners.splice(index, 1);
        }
      }
    };
  }

  emit(event, data) {
    if (this.socket?.connected) {
      this.socket.emit(event, data);
    }
  }

  subscribeToRun(runId, callback) {
    this.connect();
    this.emit('subscribe_run', { run_id: runId });
    return this.subscribe('run_update', (data) => {
      if (data.run_id === runId) {
        callback(data);
      }
    });
  }

  unsubscribeFromRun(runId) {
    this.emit('unsubscribe_run', { run_id: runId });
  }
}

export const wsService = new WebSocketService();
export default wsService;
