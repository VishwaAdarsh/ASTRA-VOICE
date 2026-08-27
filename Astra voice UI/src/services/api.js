/**
 * ASTRA API & WebSocket Communication Client.
 * Connects the React Stitch UI to the Python ASTRA Engine backend.
 */

const API_BASE_URL = 'http://127.0.0.1:8000/api/v1';
const WS_URL = 'ws://127.0.0.1:8000/api/v1/ws';

class AstraApiClient {
  constructor() {
    this.ws = null;
    this.eventListeners = new Map();
    this.isConnected = false;
    this.reconnectTimer = null;
  }

  initWebSocket() {
    try {
      this.ws = new WebSocket(WS_URL);

      this.ws.onopen = () => {
        console.log('[ASTRA Client] Connected to Python Engine WebSocket');
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
    try {
      const res = await fetch(`${API_BASE_URL}${endpoint}`, {
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
