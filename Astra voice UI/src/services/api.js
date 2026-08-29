/**
 * ASTRA API & WebSocket Communication Client.
 * Connects the React Stitch UI to the Python ASTRA Engine backend.
 * Dynamically resolves backend host and port from window.location for zero desync.
 */

function getBackendEndpoints() {
  if (typeof window !== 'undefined' && window.location && window.location.host) {
    const isDevPort = window.location.port === '5173' || window.location.port === '3000';
    const host = isDevPort ? '127.0.0.1:8000' : window.location.host;
    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const httpProto = window.location.protocol === 'https:' ? 'https:' : 'http:';
    return {
      apiBaseUrl: `${httpProto}//${host}/api/v1`,
      wsUrl: `${wsProto}//${host}/api/v1/ws`,
      host: host,
    };
  }
  return {
    apiBaseUrl: 'http://127.0.0.1:8000/api/v1',
    wsUrl: 'ws://127.0.0.1:8000/api/v1/ws',
    host: '127.0.0.1:8000',
  };
}

class AstraApiClient {
  constructor() {
    this.ws = null;
    this.eventListeners = new Map();
    this.isConnected = false;
    this.reconnectTimer = null;
    this.endpoints = getBackendEndpoints();
  }

  getApiBaseUrl() {
    this.endpoints = getBackendEndpoints();
    return this.endpoints.apiBaseUrl;
  }

  getWsUrl() {
    this.endpoints = getBackendEndpoints();
    return this.endpoints.wsUrl;
  }

  initWebSocket() {
    try {
      const wsUrl = this.getWsUrl();
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log(`[ASTRA Client] Connected to Python Engine WebSocket (${wsUrl})`);
        this.isConnected = true;
        this.emit('connection_changed', { connected: true });
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          this.emit(message.type, message);
          this.emit('*', message);
        } catch (err) {
          console.error('[ASTRA Client] Invalid WebSocket payload:', err);
        }
      };

      this.ws.onclose = () => {
        console.warn('[ASTRA Client] WebSocket disconnected. Attempting reconnect...');
        this.isConnected = false;
        this.emit('connection_changed', { connected: false });
        this.scheduleReconnect();
      };

      this.ws.onerror = (err) => {
        console.error('[ASTRA Client] WebSocket error:', err);
        this.ws.close();
      };
    } catch (e) {
      console.error('[ASTRA Client] Failed to create WebSocket connection:', e);
      this.scheduleReconnect();
    }
  }

  scheduleReconnect() {
    if (!this.reconnectTimer) {
      this.reconnectTimer = setTimeout(() => {
        this.reconnectTimer = null;
        this.initWebSocket();
      }, 3000);
    }
  }

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
      this.eventListeners.get(eventType).forEach((cb) => cb(data));
    }
  }

  // REST Helpers
  async request(endpoint, options = {}) {
    const baseUrl = this.getApiBaseUrl();
    try {
      const res = await fetch(`${baseUrl}${endpoint}`, {
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
        ...options,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(errData.detail || `HTTP Error ${res.status}`);
      }

      return await res.json();
    } catch (err) {
      console.error(`[ASTRA API Error] ${endpoint}:`, err);
      throw err;
    }
  }

  // API Methods
  async getHealth() {
    return this.request('/health');
  }

  async sendCommand(inputText) {
    return this.request('/command', {
      method: 'POST',
      body: JSON.stringify({ input: inputText }),
    });
  }

  async getTasks() {
    return this.request('/tasks');
  }

  async createTask(goalText, category = 'General') {
    return this.request('/tasks', {
      method: 'POST',
      body: JSON.stringify({ goal: goalText, category }),
    });
  }

  async getAutomations() {
    return this.request('/automations');
  }

  async createAutomation(name, schedule, actionCommand) {
    return this.request('/automations', {
      method: 'POST',
      body: JSON.stringify({ name, schedule, action_command: actionCommand }),
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
