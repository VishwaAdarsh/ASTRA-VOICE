# ASTRA V2 — API & Runtime Communication Architecture

**Phase:** V2-03  
**Status:** Canonical  
**Date:** 2026-09-16  

---

## 1. Executive Summary & Core Principles

The ASTRA V2 runtime communication subsystem bridges the PySide6/FastAPI desktop runtime and the React 19 UI. 

In Phase V2-03, this pipeline is hardened around four foundational principles:
1. **Authoritative Backend Truth:** The Python ASTRA runtime is the sole authority on state, command execution, tasks, tools, and voice lifecycle. The frontend **never fabricates** assistant actions or execution success when disconnected.
2. **Dynamic Endpoint Discovery:** Eliminates hardcoded port `8000` assumptions. The backend dynamically allocates an available port, persists the configuration, and the frontend discovers it at runtime.
3. **Strict Localhost CORS Boundary:** Eliminates insecure wildcard (`*`) CORS headers on localhost, restricting cross-origin access strictly to verified local desktop WebEngine and development origins.
4. **Idempotent & Correlated Operations:** Every user command is tagged with a client-generated UUID `request_id`. Redundant or duplicated requests within a 60-second window return the cached initial result without re-triggering execution.

```
┌─────────────────────────────────────────────────────────────┐
│                    React 19 Frontend                        │
│  - Dynamic discovery (window.__ASTRA_CONFIG__ / JSON / URL) │
│  - WebSocket client with exponential backoff & heartbeat    │
│  - Zero offline fabrication (honest status & toast errors)  │
└──────────────────────────────┬──────────────────────────────┘
                               │
            REST (HTTP) / WebSocket (WS) / JSON
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI Backend Server                     │
│  - Dynamic Port Allocation (bind 0 or configured port)       │
│  - Strict Origin Regex Policy (^http://(127.0.0.1|localhost)│
│  - CommandIdempotencyManager (60s TTL request cache)        │
│  - Standardized Event Envelope (type, event_id, payload)    │
│  - Normalized API Error Hierarchy                           │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 AstraAgent Execution Engine                 │
│  - LLM Subsystem (GeminiProvider / MockLLMProvider)         │
│  - Tool Registry & Safety Verification                      │
│  - Subsystem Health Manager                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Startup Sequence & Dynamic Port Discovery

### 2.1 Backend Port Binding
During application launch (`main.py`):
1. **Port Selection:** The backend attempts to bind to the specified port (default: 8000). If occupied, it automatically binds to port `0` (an OS-assigned free ephemeral port).
2. **Runtime Configuration Generation:** The authoritative host, bound port, API version, and protocol endpoints are saved via `write_runtime_config()` to:
   - `Astra voice UI/public/astra_runtime_config.json` (for Vite development server)
   - `Astra voice UI/dist/astra_runtime_config.json` (for packaged production UI)
   - `data/runtime_config.json` (for CLI & external inspection)
3. **WebEngine URL Injection:** In desktop mode, `main.py` launches `QWebEngineView` pointing directly to `http://{host}:{port}`, ensuring true same-origin execution where no CORS headers are required.

### 2.2 Frontend Discovery Waterfall
The frontend client (`Astra voice UI/src/services/api.js`) discovers the backend dynamically using a 5-step fallback cascade:
1. **Injected Global:** `window.__ASTRA_CONFIG__.api_base_url` (if preloaded by PySide6 WebChannel / script tag).
2. **URL Query Parameters:** `?api_port=XYZ` or `?api_url=...` (useful for dev testing with multiple instances).
3. **Runtime Configuration File:** Fetch `/astra_runtime_config.json` (served statically by Vite or FastAPI).
4. **Current Host Origin:** If running in WebEngine on `http://127.0.0.1:PORT`, uses window location origin.
5. **Localhost Probe Fallback:** Attempts sequential health probes to common local ports (`8000`, `8080`, `5000`) before entering disconnected state.

---

## 3. Security & CORS Policy

ASTRA V2 explicitly avoids `allow_origins=["*"]`. Exposing a wildcard CORS endpoint on localhost opens users to **Cross-Site Port Attacks (CSPA)**, where malicious websites visited in an external browser can issue unauthenticated HTTP requests to `http://localhost:8000/api/v1/command`.

### Enforced Rules:
- **Explicit Allowed Origins:** `http://127.0.0.1:5173`, `http://localhost:5173`, `http://localhost:3000`, and the active bound port origin.
- **Strict Localhost Regex:** `r"^http://(127\.0\.0\.1|localhost)(:\d+)?$"` permits local developer tools and desktop WebEngine while rejecting external browser origins (e.g., `evil-site.com`).
- **Credentials Allowed:** Controlled cross-origin requests allow credentials only within the regex match.

---

## 4. Standardized API Contracts

### 4.1 REST Endpoints

| Method | Path | Description | Request Payload | Response Envelope |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/ready` | Readiness probe | None | `{"status": "ready", "version": "...", "subsystems": {...}}` |
| `GET` | `/api/v1/health` | Health & diagnostics | None | `{"status": "healthy"|"degraded", "uptime_s": 42.1, ...}` |
| `GET` | `/api/v1/config` | Runtime discovery | None | `{"api_base_url": "...", "ws_url": "...", "version": "..."}` |
| `POST` | `/api/v1/command` | Dispatch command | `{"text": "...", "request_id": "uuid"}` | `{"success": true, "response": "...", "request_id": "uuid"}` |
| `POST` | `/api/v1/agent/reset`| Reset conversation | None | `{"status": "reset", "message": "..."}` |
| `GET` | `/api/v1/tasks` | Get active tasks | None | `{"tasks": [...]}` |

### 4.2 Idempotency Handling (`POST /api/v1/command`)
To prevent accidental duplicate execution caused by network hiccups, rapid clicks, or retry loops:
- Every command request includes an optional or generated `request_id` (UUID v4).
- `CommandIdempotencyManager` caches executed command results for **60 seconds**.
- If a duplicate `request_id` arrives while in-flight, it returns an acknowledgment indicating the command is already processing.
- If a duplicate `request_id` arrives after completion, it returns the cached result immediately with `"cached": true`, avoiding duplicate agent steps or side effects.

### 4.3 Normalized Error Responses
All endpoints return standard error structures with machine-readable error codes:
```json
{
  "error": {
    "code": "QUOTA_EXHAUSTED",
    "message": "AI quota exhausted. Please check your Gemini billing or quota.",
    "status_code": 429,
    "timestamp": 1726477000.123,
    "request_id": "b9f2910e-8f52-4cf4-a78b-0c25a07c1234"
  }
}
```

Standard error codes:
- `AUTH_FAILED` (401): Missing or invalid Gemini API key.
- `QUOTA_EXHAUSTED` (429): Upstream provider rate limit or exhaustion.
- `TIMEOUT` (504): LLM or tool execution timeout.
- `SAFETY_BLOCKED` (403): Content or tool safety violation.
- `INTERNAL_ERROR` (500): Unhandled backend exception.

---

## 5. Standardized WebSocket Protocol

WebSocket connection endpoint: `/api/v1/ws`

### 5.1 Event Envelope Format
All messages sent from the backend follow a standardized event envelope:
```json
{
  "type": "state_change" | "command_response" | "task_update" | "voice_state" | "pong" | "error",
  "event_id": "evt_1726477000_abcd",
  "timestamp": 1726477000.456,
  "request_id": "b9f2910e-8f52-4cf4-a78b-0c25a07c1234",
  "payload": { ... }
}
```
*(Legacy top-level keys like `state`, `response`, `data` are preserved for backward compatibility).*

### 5.2 Heartbeat Protocol
- The frontend sends periodic `{ "type": "ping", "timestamp": Date.now() }` every 15 seconds.
- The backend immediately echoes `{ "type": "pong", "timestamp": Date.now(), "client_timestamp": ... }`.
- Missed heartbeats trigger clean reconnection logic before the socket silently dies.

### 5.3 Bounded Reconnection Strategy
The React frontend implements a finite exponential backoff reconnect policy:
- **Base Backoff:** 1,000 ms
- **Backoff Multiplier:** 1.5x with +/- 20% jitter
- **Max Backoff:** 15,000 ms
- **Max Retries:** 20 attempts
- When retries are exhausted, the client transitions to `FAILED` state and prompts the user with an engine restart button instead of continuously thrashing the network.

---

## 6. Frontend / Backend Separation (Zero-Fabrication)

### 6.1 Elimination of Fake Offline Execution
Previous iterations simulated task creation, reminder scheduling, and note-taking entirely in React `useState` when the backend was unreachable. 

In ASTRA V2:
- **No Client Hallucination:** The frontend never marks a command as "Executed" or creates fake tasks locally.
- **Interrupted State Machine:** If connection drops mid-command, the command status enters `INTERRUPTED` rather than falsely declaring failure or retry duplication.
- **Honest UI Indicators:** When the backend is offline:
  - Header displays a distinct amber/red `Engine Offline` or `Reconnecting...` badge.
  - Action buttons (Microphone, Command submission) display disabled states or surface descriptive toast notifications.
  - Chat logs clearly present an engine disconnect message with troubleshooting instructions.
