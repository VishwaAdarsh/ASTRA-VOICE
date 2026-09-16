"""
ASTRA FastAPI & WebSocket Communication Server (Phase V2-03 Upgraded).
Bridges the React Stitch UI (frontend) with the Python ASTRA Engine (backend).
Features dynamic endpoint discovery, bounded WebSocket envelopes, request correlation,
idempotency protection, localhost CORS restrictions, and normalized error responses.
"""

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Any, Optional
import uuid

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.brain.llm.errors import (
    LLMAuthError,
    LLMConfigError,
    LLMContentPolicyError,
    LLMInvalidRequestError,
    LLMModelNotFoundError,
    LLMNetworkError,
    LLMProviderError,
    LLMQuotaExhaustedError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)
from src.core.config import Config
from src.core.logger import get_logger
from src.memory.models import MemoryType
from src.security.auditor import SecretRedactionFilter

logger = get_logger()


# ============================================================================
# Request / Response Schemas
# ============================================================================

class CommandRequest(BaseModel):
    input: str
    request_id: Optional[str] = None


class TaskRequest(BaseModel):
    goal: str
    category: Optional[str] = "General"
    priority: Optional[str] = "medium"


class AutomationRequest(BaseModel):
    name: str
    schedule: str
    action_command: str
    category: Optional[str] = "Personal"


class MemoryRequest(BaseModel):
    content: str
    type: Optional[str] = "USER_FACT"


class VoiceSpeakRequest(BaseModel):
    text: str


class SecurityConfirmRequest(BaseModel):
    request_id: str
    confirmed: bool


# ============================================================================
# Idempotency Cache Manager
# ============================================================================

class CommandIdempotencyManager:
    """Caches recent command responses to prevent duplicate executions from UI retries/reconnects."""

    def __init__(self, ttl_seconds: float = 60.0):
        self.ttl = ttl_seconds
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}

    def get(self, request_id: Optional[str]) -> Optional[dict[str, Any]]:
        if not request_id:
            return None
        self._clean()
        if request_id in self._cache:
            _, response = self._cache[request_id]
            logger.info(f"[API] Returning cached idempotent response for request_id: {request_id}")
            return response
        return None

    def set(self, request_id: Optional[str], response: dict[str, Any]) -> None:
        if not request_id:
            return
        self._clean()
        self._cache[request_id] = (time.time(), response)

    def _clean(self):
        now = time.time()
        expired = [k for k, (t, _) in self._cache.items() if now - t > self.ttl]
        for k in expired:
            del self._cache[k]


idempotency_manager = CommandIdempotencyManager()


# ============================================================================
# WebSocket Connection Manager
# ============================================================================

class ConnectionManager:
    """Manages active WebSocket connections to push real-time events to React frontend."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info("WebSocket client disconnected.")

    async def broadcast(
        self,
        event_type: str,
        payload: dict[str, Any],
        request_id: Optional[str] = None,
    ):
        """Broadcast standardized envelope while preserving legacy fields for backwards compatibility."""
        now_iso = datetime.now(timezone.utc).isoformat()
        event_id = f"evt-{uuid.uuid4().hex[:10]}"

        envelope = {
            "type": event_type,
            "event_id": event_id,
            "timestamp": now_iso,
            "request_id": request_id,
            "payload": payload,
            **payload,  # Legacy top-level fields for existing UI components
        }

        clean_data = json.loads(SecretRedactionFilter.redact(json.dumps(envelope)))
        for connection in list(self.active_connections):
            try:
                await connection.send_json(clean_data)
            except Exception as e:
                logger.warning(f"Error broadcasting to WebSocket client: {e}")
                self.disconnect(connection)

    async def shutdown(self):
        """Notify all active connections and close cleanly."""
        await self.broadcast("ENGINE_SHUTDOWN", {"message": "ASTRA Engine is shutting down"})
        for connection in list(self.active_connections):
            try:
                await connection.close(code=1001, reason="Server shutdown")
            except Exception:
                pass
        self.active_connections.clear()


ws_manager = ConnectionManager()


# ============================================================================
# Error Normalization Helper
# ============================================================================

def normalize_api_error(e: Exception, request_id: Optional[str] = None) -> tuple[int, dict[str, Any]]:
    """Maps internal exceptions to standardized HTTP status and error envelope."""
    now_iso = datetime.now(timezone.utc).isoformat()
    if isinstance(e, LLMQuotaExhaustedError):
        code = "LLM_QUOTA_EXHAUSTED"
        msg = "The configured AI provider has reached its daily quota."
        status = 429
    elif isinstance(e, LLMAuthError):
        code = "LLM_AUTH_FAILED"
        msg = "AI provider authentication failed. Check your API key."
        status = 401
    elif isinstance(e, LLMRateLimitError):
        code = "RATE_LIMITED"
        msg = "AI provider rate limit reached. Please wait a moment."
        status = 429
    elif isinstance(e, LLMConfigError):
        code = "INVALID_CONFIGURATION"
        msg = "AI provider configuration error."
        status = 500
    elif isinstance(e, LLMContentPolicyError):
        code = "CONTENT_POLICY_VIOLATION"
        msg = "Request was blocked by safety policy filters."
        status = 400
    elif isinstance(e, LLMModelNotFoundError):
        code = "MODEL_NOT_FOUND"
        msg = "Configured AI model was not found."
        status = 404
    elif isinstance(e, (TimeoutError, LLMTimeoutError)):
        code = "TIMEOUT"
        msg = "Command execution timed out."
        status = 504
    elif isinstance(e, (ConnectionError, LLMNetworkError)):
        code = "NETWORK_ERROR"
        msg = "Network connection to upstream provider failed."
        status = 503
    elif isinstance(e, PermissionError):
        code = "PERMISSION_DENIED"
        msg = "Permission authorization denied."
        status = 403
    else:
        code = "EXECUTION_ERROR"
        msg = str(e)
        status = 500

    error_payload = {
        "success": False,
        "error": {
            "code": code,
            "message": msg,
            "details": str(e),
        },
        "request_id": request_id,
        "timestamp": now_iso,
    }
    return status, error_payload


# ============================================================================
# FastAPI Application Factory
# ============================================================================

def create_app(
    agent=None,
    voice_manager=None,
    port: int = 8000,
    host: str = "127.0.0.1",
    runtime_config: Optional[dict[str, Any]] = None,
) -> FastAPI:
    """Factory creating FastAPI application bound to AstraAgent, VoiceManager, and dynamic runtime info."""
    app = FastAPI(title="ASTRA Engine API", version="1.0.0")

    # Localhost Security: Restrict CORS to local WebEngine and development origins
    allowed_origins = [
        f"http://{host}:{port}",
        f"http://127.0.0.1:{port}",
        f"http://localhost:{port}",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_origin_regex=r"^http://(127\.0\.0\.1|localhost)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # Attach agent, voice_manager, and lifecycle state
    app.state.agent = agent
    app.state.voice_manager = voice_manager
    app.state.port = port
    app.state.host = host
    app.state.runtime_config = runtime_config
    app.state.lifecycle_state = "READY"
    app.state.ws_manager = ws_manager
    app.state.idempotency_manager = idempotency_manager

    # -------------------------------
    # Dynamic Runtime Configuration & Readiness
    # -------------------------------
    @app.get("/api/v1/config")
    @app.get("/api/v1/runtime-config")
    async def get_runtime_config():
        """Expose dynamic runtime configuration for frontend discovery without hardcoded ports."""
        if app.state.runtime_config:
            return app.state.runtime_config
        return {
            "apiBaseUrl": f"http://{host}:{port}/api/v1",
            "wsUrl": f"ws://{host}:{port}/api/v1/ws",
            "host": f"{host}:{port}",
            "port": port,
            "version": "1.0.0",
            "environment": "desktop",
            "capabilities": ["text", "voice", "tools", "vision", "memory", "automations"],
        }

    @app.get("/api/v1/ready")
    async def get_readiness():
        """Readiness probe distinguishing process start from full ASTRA readiness."""
        is_agent_ready = app.state.agent is not None
        is_server_ready = app.state.lifecycle_state == "READY"
        is_healthy = False
        if is_agent_ready and hasattr(app.state.agent, "health_manager"):
            is_healthy = app.state.agent.health_manager.is_overall_healthy()

        ready = is_agent_ready and is_server_ready
        return {
            "ready": ready,
            "status": "READY" if ready else "STARTING",
            "lifecycle_state": app.state.lifecycle_state,
            "subsystems_ready": is_healthy,
            "agent_initialized": is_agent_ready,
        }

    # -------------------------------
    # WebSocket Real-Time Endpoint
    # -------------------------------
    @app.websocket("/api/v1/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await ws_manager.connect(websocket)
        try:
            # Send initial state snapshot on connection
            if app.state.agent:
                health = app.state.agent.health_manager.get_all_health()
                health_data = {k: v.status.value for k, v in health.items()}
                await ws_manager.broadcast("HEALTH_CHANGED", {"data": health_data, "subsystems": health_data})

            while True:
                data = await websocket.receive_json()
                msg_type = (data.get("type") or "").upper()
                if msg_type == "PING":
                    await websocket.send_json({
                        "type": "PONG",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "client_timestamp": data.get("timestamp"),
                    })
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            ws_manager.disconnect(websocket)

    # -------------------------------
    # Health Diagnostics
    # -------------------------------
    @app.get("/api/v1/health")
    async def get_health():
        if not app.state.agent:
            return {"status": "DEGRADED", "subsystems": {}}
        health_dict = app.state.agent.health_manager.get_all_health()
        subsystems = {}
        for sub_name, sub_health in health_dict.items():
            subsystems[sub_name] = {
                "status": sub_health.status.value,
                "message": sub_health.message,
            }
        return {
            "status": "HEALTHY" if app.state.agent.health_manager.is_overall_healthy() else "DEGRADED",
            "subsystems": subsystems,
        }

    # -------------------------------
    # Command Execution (Brain & LLM)
    # -------------------------------
    @app.post("/api/v1/command")
    async def process_command(req: CommandRequest):
        if not app.state.agent:
            raise HTTPException(status_code=503, detail="ASTRA Engine agent not initialized")

        req_id = req.request_id or f"req-{uuid.uuid4().hex[:8]}"

        # Check Idempotency Cache: prevent duplicate execution
        cached = idempotency_manager.get(req_id)
        if cached:
            return cached

        logger.info(f"API Command Received: '{req.input}' (request_id={req_id})")
        await ws_manager.broadcast("BRAIN_STARTED", {"input": req.input}, request_id=req_id)

        try:
            # Run in thread pool to avoid blocking async event loop
            raw_res = await asyncio.to_thread(app.state.agent.process_command, req.input)
            if isinstance(raw_res, tuple):
                response_text, tool_result = raw_res
            else:
                response_text = str(raw_res)
                tool_result = None

            tool_used = getattr(tool_result, "tool_name", None) if tool_result else None
            exec_time = getattr(tool_result, "execution_time_sec", 0.0) if tool_result else 0.0
            status_val = (
                tool_result.status.value
                if (tool_result and hasattr(tool_result.status, "value"))
                else "SUCCESS"
            )

            now_iso = datetime.now(timezone.utc).isoformat()
            response_payload = {
                "success": True,
                "type": "BRAIN_COMPLETED",
                "request_id": req_id,
                "timestamp": now_iso,
                "status": status_val,
                "input": req.input,
                "response": response_text,
                "tool_used": tool_used,
                "widgetType": "ASSISTANT_RESPONSE",
                "widgetData": {
                    "tool_used": tool_used,
                    "execution_time_sec": exec_time,
                },
                "data": {
                    "response": response_text,
                    "tool_used": tool_used,
                    "status": status_val,
                },
            }

            # Cache completed response in idempotency cache
            idempotency_manager.set(req_id, response_payload)

            await ws_manager.broadcast("BRAIN_COMPLETED", response_payload, request_id=req_id)

            # Auto TTS if voice manager is active
            if app.state.voice_manager and getattr(app.state.agent.config, "voice_enabled", True):
                asyncio.create_task(asyncio.to_thread(app.state.voice_manager.speak, response_text))

            return response_payload

        except Exception as e:
            logger.error(f"Error processing command via API: {e}")
            status_code, err_payload = normalize_api_error(e, request_id=req_id)
            await ws_manager.broadcast("ERROR_OCCURRED", err_payload, request_id=req_id)
            return JSONResponse(status_code=status_code, content=err_payload)

    # -------------------------------
    # Task Engine (Phase 9)
    # -------------------------------
    @app.get("/api/v1/tasks")
    async def list_tasks():
        if not app.state.agent:
            return []
        tasks = app.state.agent.task_manager.list_recent_tasks()
        return [
            {
                "id": f"tsk-{t.id}",
                "title": getattr(t, "goal", getattr(t, "description", "Task")),
                "status": t.status.value if hasattr(t.status, "value") else str(t.status),
                "progress": 100 if (hasattr(t.status, "value") and t.status.value == "COMPLETED") else 0,
                "category": getattr(t, "category", "Development"),
                "completed": hasattr(t.status, "value") and t.status.value == "COMPLETED",
                "priority": "high",
                "dueDate": t.created_at[:10] if hasattr(t, "created_at") and t.created_at else "Today",
            }
            for t in tasks
        ]

    @app.post("/api/v1/tasks")
    async def create_task(req: TaskRequest):
        if not app.state.agent:
            raise HTTPException(status_code=503, detail="ASTRA Engine agent not initialized")
        task = await asyncio.to_thread(app.state.agent.task_manager.create_and_execute_goal, req.goal)
        await ws_manager.broadcast({"type": "TASK_STARTED", "task_id": getattr(task, "task_id", getattr(task, "id", "task_1")), "goal": req.goal})
        return {
            "id": f"tsk-{getattr(task, 'task_id', getattr(task, 'id', 'task_1'))}",
            "title": req.goal,
            "status": task.status.value if hasattr(task.status, "value") else str(task.status),
            "completed": False,
        }

    # -------------------------------
    # Automation Engine (Phase 10)
    # -------------------------------
    @app.get("/api/v1/automations")
    async def list_automations():
        if not app.state.agent:
            return []
        automations = app.state.agent.automation_manager.list_automations()
        return [
            {
                "id": f"rem-{a.id}",
                "title": a.name,
                "time": a.trigger_config.get("schedule", a.trigger_type.value if hasattr(a.trigger_type, "value") else str(a.trigger_type)),
                "date": "Active" if (hasattr(a.status, "value") and a.status.value == "ACTIVE") else "Paused",
                "category": getattr(a, "category", "Work"),
                "completed": hasattr(a.status, "value") and a.status.value != "ACTIVE",
                "priority": "high",
            }
            for a in automations
        ]


    @app.post("/api/v1/automations")
    async def create_automation(req: AutomationRequest):
        if not app.state.agent:
            raise HTTPException(status_code=503, detail="ASTRA Engine agent not initialized")
        automation = await asyncio.to_thread(
            app.state.agent.automation_manager.create_automation,
            req.name,
            req.schedule,
            req.action_command,
        )
        return {
            "id": f"rem-{automation.id}",
            "title": automation.name,
            "time": automation.cron_expression,
            "date": "Today",
            "category": req.category,
            "completed": False,
        }

    # -------------------------------
    # Memory Subsystem (Phase 7)
    # -------------------------------
    @app.get("/api/v1/memory")
    async def list_memories(q: Optional[str] = None):
        if not app.state.agent:
            return []
        if q:
            memories = app.state.agent.memory_manager.search(query=q)
        else:
            memories = app.state.agent.memory_manager.list_all()

        return [
            {
                "id": f"not-{m.id}",
                "title": m.content[:40] + ("..." if len(m.content) > 40 else ""),
                "body": m.content,
                "date": m.created_at[:10],
                "tags": [m.type.value, m.source.value],
                "color": "#7c5cfc",
            }
            for m in memories
        ]

    @app.post("/api/v1/memory")
    async def add_memory(req: MemoryRequest):
        if not app.state.agent:
            raise HTTPException(status_code=503, detail="ASTRA Engine agent not initialized")
        mem_type = MemoryType.USER_FACT
        if req.type and req.type in MemoryType.__members__:
            mem_type = MemoryType[req.type]

        memory = await asyncio.to_thread(
            app.state.agent.memory_manager.remember,
            content=req.content,
            memory_type=mem_type,
        )
        return {
            "id": f"not-{memory.id}",
            "title": memory.content[:40],
            "body": memory.content,
            "date": memory.created_at[:10],
            "tags": [memory.type.value],
            "color": "#7c5cfc",
        }

    # -------------------------------
    # Vision Subsystem (Phase 8)
    # -------------------------------
    @app.get("/api/v1/vision")
    async def get_vision():
        if not app.state.agent:
            raise HTTPException(status_code=503, detail="ASTRA Engine agent not initialized")
        context = await asyncio.to_thread(app.state.agent.vision_manager.analyze_active_window)
        return {
            "app_name": context.app_name,
            "window_title": context.window_title,
            "description": context.description,
            "ocr_text": context.ocr.full_text,
            "detected_elements_count": len(context.elements),
        }

    # -------------------------------
    # Configuration & Settings
    # -------------------------------
    @app.get("/api/v1/settings")
    async def get_settings():
        if not app.state.agent:
            return {}
        cfg = app.state.agent.config
        return {
            "voiceName": "Aura",
            "speechRate": 1.0,
            "speechPitch": 1.0,
            "wakeWord": True,
            "soundEffects": True,
            "autoSpeak": True,
            "theme": "dark",
            "llm_provider": cfg.llm_provider,
            "llm_model": cfg.llm_model,
            "stt_provider": cfg.stt_provider,
            "tts_provider": cfg.tts_provider,
            "permissions_mode": cfg.permissions_mode,
            "version": "1.0.0",
        }

    # -------------------------------
    # Voice Controls
    # -------------------------------
    @app.post("/api/v1/voice/listen")
    async def voice_listen():
        if not app.state.voice_manager:
            raise HTTPException(status_code=503, detail="VoiceManager not available")

        await ws_manager.broadcast({"type": "VOICE_STATE_CHANGED", "state": "listening"})
        response_text, tool_result = await asyncio.to_thread(app.state.voice_manager.listen_and_process, None)
        await ws_manager.broadcast({"type": "VOICE_STATE_CHANGED", "state": "idle"})
        return {"status": "completed", "response": response_text}

    @app.post("/api/v1/voice/speak")
    async def voice_speak(req: VoiceSpeakRequest):
        if not app.state.voice_manager:
            raise HTTPException(status_code=503, detail="VoiceManager not available")
        await ws_manager.broadcast({"type": "VOICE_STATE_CHANGED", "state": "speaking"})
        await asyncio.to_thread(app.state.voice_manager.speak, req.text)
        await ws_manager.broadcast({"type": "VOICE_STATE_CHANGED", "state": "idle"})
        return {"status": "completed"}

    @app.post("/api/v1/voice/stop")
    async def voice_stop():
        if not app.state.voice_manager:
            raise HTTPException(status_code=503, detail="VoiceManager not available")
        app.state.voice_manager.stop_speaking()
        await ws_manager.broadcast({"type": "VOICE_STATE_CHANGED", "state": "idle"})
        return {"status": "stopped"}

    # -------------------------------
    # Static Files Mounting (React Build)
    # -------------------------------
    dist_dir = Path(__file__).resolve().parent.parent.parent / "Astra voice UI" / "dist"
    if dist_dir.exists():
        app.mount("/", StaticFiles(directory=dist_dir, html=True), name="static")
        logger.info(f"Mounted React dist static directory: {dist_dir}")
    else:
        logger.warning(f"React dist directory not found at {dist_dir}. Serve dev server or build frontend.")

    return app
