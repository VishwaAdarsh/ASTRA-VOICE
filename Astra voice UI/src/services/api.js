/**
 * ASTRA API & WebSocket Communication Client (Phase V2-03 Upgraded).
 * Single authoritative client for FastAPI & WebSocket runtime communication.
 * Implements dynamic endpoint discovery, bounded reconnect backoff, heartbeat,
 * request correlation, and error normalization.
 */

// Connection State Enum
export const ConnectionState = {
  DISCONNECTED: 'DISCONNECTED',
  CONNECTING: 'CONNECTING',
  CONNECTED: 'CONNECTED',
  RECONNECTING: 'RECONNECTING',
  FAILED: 'FAILED',
};

// Known Standard WebSocket Events
export const WebSocketEventType = {
  HEALTH_CHANGED: 'HEALTH_CHANGED',
  BRAIN_STARTED: 'BRAIN_STARTED',
  BRAIN_COMPLETED: 'BRAIN_COMPLETED',
  VOICE_STATE_CHANGED: 'VOICE_STATE_CHANGED',
  ERROR_OCCURRED: 'ERROR_OCCURRED',
  TASK_STARTED: 'TASK_STARTED',
  ENGINE_SHUTDOWN: 'ENGINE_SHUTDOWN',
  PING: 'PING',
  PONG: 'PONG',
};

/**
 * Generate a unique request correlation ID.
 */
export function generateRequestId() {
  return `req-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

class AstraApiClient {
  constructor() {
    this.ws = null;
    this.eventListeners = new Map();
    this.connectionState = ConnectionState.DISCONNECTED;
    this.isConnected = false;

    // Bounded Reconnection
    this.reconnectTimer = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 20;
    this.initialBackoffMs = 1000;
    this.maxBackoffMs = 15000;

    // Heartbeat
    this.heartbeatTimer = null;
    this.heartbeatIntervalMs = 15000;
    this.lastPongTime = 0;

    // Dynamic Endpoints
    this.endpoints = this.resolveInitialEndpoints();
    this.isConfigLoaded = false;
  }

  /**
   * Synchronously resolve best-guess endpoints before async discovery completes.
   */
  resolveInitialEndpoints() {
    if (typeof window !== 'undefined') {
      // 1. Injected global config (e.g. from desktop shell)
      if (window.__ASTRA_CONFIG__ && window.__ASTRA_CONFIG__.apiBaseUrl) {
        return {
          apiBaseUrl: window.__ASTRA_CONFIG__.apiBaseUrl,
          wsUrl: window.__ASTRA_CONFIG__.wsUrl,
          host: window.__ASTRA_CONFIG__.host || window.location.host,
        };
      }

      // 2. URL search parameters (?apiBaseUrl=... or ?port=...)
      const params = new URLSearchParams(window.location.search);
      const paramPort = params.get('port');
      const paramApi = params.get('apiBaseUrl');
      const paramWs = params.get('wsUrl');
      if (paramApi && paramWs) {
        return { apiBaseUrl: paramApi, wsUrl: paramWs, host: window.location.host };
      }
      if (paramPort) {
        const host = `127.0.0.1:${paramPort}`;
        return {
          apiBaseUrl: `http://${host}/api/v1`,
          wsUrl: `ws://${host}/api/v1/ws`,
          host: host,
        };
      }

      // 3. Same-origin fallback (when served directly from FastAPI WebEngine)
      if (window.location.host) {
        const isDevPort = window.location.port === '5173' || window.location.port === '3000';
        if (!isDevPort) {
          const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
          const httpProto = window.location.protocol === 'https:' ? 'https:' : 'http:';
          return {
            apiBaseUrl: `${httpProto}//${window.location.host}/api/v1`,
            wsUrl: `${wsProto}//${window.location.host}/api/v1/ws`,
            host: window.location.host,
          };
        }
      }
    }

    // Default development fallback
    return {
      apiBaseUrl: 'http://127.0.0.1:8000/api/v1',
      wsUrl: 'ws://127.0.0.1:8000/api/v1/ws',
      host: '127.0.0.1:8000',
    };
  }

  /**
   * Asynchronously discover dynamic runtime endpoints from backend or runtime config.
   */
  async discoverEndpoints() {
    if (this.isConfigLoaded) return this.endpoints;

    // 1. Try reading runtime configuration file published by backend
    try {
      const res = await fetch('/astra_runtime_config.json', { cache: 'no-store' });
      if (res.ok) {
        const data = await res.json();
        if (data.apiBaseUrl && data.wsUrl) {
          this.endpoints = {
            apiBaseUrl: data.apiBaseUrl,
            wsUrl: data.wsUrl,
            host: data.host || '127.0.0.1:8000',
          };
          this.isConfigLoaded = true;
          console.log('[ASTRA Discovery] Loaded runtime config:', this.endpoints);
          return this.endpoints;
        }
      }
    } catch (e) {
      // Ignore and proceed to probe fallback
    }

    // 2. If running on dev port and config file not loaded, probe localhost ports
    if (typeof window !== 'undefined' && (window.location.port === '5173' || window.location.port === '3000')) {
      const probePorts = [8000, 8001, 8002, 8003];
      for (const p of probePorts) {
        try {
          const ctrl = new AbortController();
          const timer = setTimeout(() => ctrl.abort(), 800);
          const probeRes = await fetch(`http://127.0.0.1:${p}/api/v1/ready`, { signal: ctrl.signal });
          clearTimeout(timer);
          if (probeRes.ok) {
            this.endpoints = {
              apiBaseUrl: `http://127.0.0.1:${p}/api/v1`,
              wsUrl: `ws://127.0.0.1:${p}/api/v1/ws`,
              host: `127.0.0.1:${p}`,
            };
            this.isConfigLoaded = true;
            console.log(`[ASTRA Discovery] Discovered active backend on port ${p}`);
            return this.endpoints;
          }
        } catch (_) {
          continue;
        }
      }
    }

    return this.endpoints;
  }

  getApiBaseUrl() {
    return this.endpoints.apiBaseUrl;
  }

  getWsUrl() {
    return this.endpoints.wsUrl;
  }

  // ==========================================================================
  // WebSocket Lifecycle
  // ==========================================================================

  async initWebSocket() {
    // Ensure endpoints are resolved
    await this.discoverEndpoints();

    // Avoid duplicate connections
    if (this.ws && (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN)) {
      return;
    }

    this.setConnectionState(ConnectionState.CONNECTING);
    const wsUrl = this.getWsUrl();

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log(`[ASTRA WebSocket] Connected to Engine at ${wsUrl}`);
        this.reconnectAttempts = 0;
        this.setConnectionState(ConnectionState.CONNECTED);
        this.startHeartbeat();
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          const eventType = message.type || 'UNKNOWN';

          if (eventType === 'PONG') {
            this.lastPongTime = Date.now();
            return;
          }

          // Emit typed event
          this.emit(eventType, message);
          this.emit('*', message);
        } catch (err) {
          console.warn('[ASTRA WebSocket] Non-JSON payload received:', event.data);
        }
      };

      this.ws.onclose = (event) => {
        console.warn(`[ASTRA WebSocket] Connection closed (code: ${event.code})`);
        this.stopHeartbeat();
        this.setConnectionState(ConnectionState.DISCONNECTED);
        this.scheduleReconnect();
      };

      this.ws.onerror = (err) => {
        console.error('[ASTRA WebSocket] Socket error:', err);
        try {
          this.ws.close();
        } catch (_) {}
      };
    } catch (e) {
      console.error('[ASTRA WebSocket] Failed to initialize socket:', e);
      this.setConnectionState(ConnectionState.DISCONNECTED);
      this.scheduleReconnect();
    }
  }

  disconnect() {
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      try {
        this.ws.close(1000, 'Client closed connection');
      } catch (_) {}
      this.ws = null;
    }
    this.setConnectionState(ConnectionState.DISCONNECTED);
  }

  setConnectionState(state) {
    this.connectionState = state;
    this.isConnected = state === ConnectionState.CONNECTED;
    this.emit('connection_changed', {
      connected: this.isConnected,
      state: state,
    });
  }

  scheduleReconnect() {
    if (this.reconnectTimer) return;

    this.reconnectAttempts++;
    if (this.reconnectAttempts > this.maxReconnectAttempts) {
      console.error('[ASTRA WebSocket] Reconnect attempts exhausted.');
      this.setConnectionState(ConnectionState.FAILED);
      return;
    }

    // Bounded exponential backoff
    const delay = Math.min(
      this.initialBackoffMs * Math.pow(1.8, this.reconnectAttempts - 1),
      this.maxBackoffMs
    );

    this.setConnectionState(ConnectionState.RECONNECTING);
    console.log(`[ASTRA WebSocket] Reconnecting in ${(delay / 1000).toFixed(1)}s (attempt ${this.reconnectAttempts})...`);

    this.reconnectTimer = setTimeout(async () => {
      this.reconnectTimer = null;
      // Re-discover endpoints before reconnecting in case backend restarted on alternate port
      await this.discoverEndpoints();
      this.initWebSocket();
    }, delay);
  }

  startHeartbeat() {
    this.stopHeartbeat();
    this.lastPongTime = Date.now();
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        try {
          this.ws.send(JSON.stringify({ type: 'PING', timestamp: Date.now() }));
        } catch (_) {}
      }
    }, this.heartbeatIntervalMs);
  }

  stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  // ==========================================================================
  // Event Subscription
  // ==========================================================================

  on(eventType, callback) {
    if (!this.eventListeners.has(eventType)) {
      this.eventListeners.set(eventType, new Set());
    }
    this.eventListeners.get(eventType).add(callback);
    return () => this.off(eventType, callback);
  }

  off(eventType, callback) {
    if (this.eventListeners.has(eventType)) {
      this.eventListeners.get(eventType).delete(callback);
    }
  }

  emit(eventType, data) {
    if (this.eventListeners.has(eventType)) {
      this.eventListeners.get(eventType).forEach((cb) => {
        try {
          cb(data);
        } catch (e) {
          console.error(`[ASTRA Client] Error in listener for ${eventType}:`, e);
        }
      });
    }
  }

  // ==========================================================================
  // REST API Execution
  // ==========================================================================

  async request(endpoint, options = {}, timeoutMs = 30000) {
    const baseUrl = this.getApiBaseUrl();
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const res = await fetch(`${baseUrl}${endpoint}`, {
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
        ...options,
      });

      clearTimeout(timer);

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        const normalizedMsg =
          (errData.error && errData.error.message) ||
          errData.detail ||
          `HTTP ${res.status}: ${res.statusText}`;
        const error = new Error(normalizedMsg);
        error.status = res.status;
        error.code = errData.error?.code || `HTTP_${res.status}`;
        error.details = errData.error?.details || errData.detail;
        throw error;
      }

      return await res.json();
    } catch (err) {
      clearTimeout(timer);
      if (err.name === 'AbortError') {
        const timeoutErr = new Error('Request timed out after 30 seconds.');
        timeoutErr.code = 'TIMEOUT';
        throw timeoutErr;
      }
      console.error(`[ASTRA API Error] ${endpoint}:`, err);
      throw err;
    }
  }

  // ==========================================================================
  // Public API Endpoints
  // ==========================================================================

  async getHealth() {
    return this.request('/health', {}, 5000);
  }

  async getReadiness() {
    return this.request('/ready', {}, 5000);
  }

  async getRuntimeConfig() {
    return this.request('/config', {}, 5000);
  }

  async sendCommand(inputText, requestId = null) {
    const reqId = requestId || generateRequestId();
    return this.request('/command', {
      method: 'POST',
      body: JSON.stringify({ input: inputText, request_id: reqId }),
    });
  }

  async getTasks() {
    return this.request('/tasks');
  }

  async createTask(goalText, category = 'General', priority = 'medium') {
    return this.request('/tasks', {
      method: 'POST',
      body: JSON.stringify({ goal: goalText, category, priority }),
    });
  }

  async getAutomations() {
    return this.request('/automations');
  }

  async createAutomation(name, schedule, actionCommand, category = 'Personal') {
    return this.request('/automations', {
      method: 'POST',
      body: JSON.stringify({
        name,
        schedule,
        action_command: actionCommand,
        category,
      }),
    });
  }

  async getMemories(query = '') {
    const qStr = query ? `?q=${encodeURIComponent(query)}` : '';
    return this.request(`/memory${qStr}`);
  }

  async addMemory(contentText, type = 'USER_FACT') {
    return this.request('/memory', {
      method: 'POST',
      body: JSON.stringify({ content: contentText, type }),
    });
  }

  async getVision() {
    return this.request('/vision');
  }

  async getSettings() {
    return this.request('/settings');
  }

  async triggerVoiceListen() {
    return this.request('/voice/listen', { method: 'POST' });
  }

  async triggerVoiceSpeak(text) {
    return this.request('/voice/speak', {
      method: 'POST',
      body: JSON.stringify({ text }),
    });
  }

  async triggerVoiceStop() {
    return this.request('/voice/stop', { method: 'POST' });
  }
}

export const astraApi = new AstraApiClient();
