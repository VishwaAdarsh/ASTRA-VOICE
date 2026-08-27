"""
ASTRA FastAPI & WebSocket Communication Server.
Bridges the React Stitch UI (frontend) with the Python ASTRA Engine (backend).
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.core.config import Config
from src.core.logger import get_logger
from src.memory.models import MemoryType
from src.security.auditor import SecretRedactionFilter

logger = get_logger()


# Request / Response Schemas
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

    async def broadcast(self, message: dict[str, Any]):
        clean_data = json.loads(SecretRedactionFilter.redact(json.dumps(message)))
        for connection in list(self.active_connections):
            try:
                await connection.send_json(clean_data)
            except Exception as e:
                logger.warning(f"Error broadcasting to WebSocket client: {e}")
                self.disconnect(connection)


ws_manager = ConnectionManager()


def create_app(agent=None, voice_manager=None) -> FastAPI:
    """Factory creating FastAPI application bound to AstraAgent and VoiceManager."""
    app = FastAPI(title="ASTRA Engine API", version="1.0.0")

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Attach agent and voice_manager instances
    app.state.agent = agent
    app.state.voice_manager = voice_manager

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
                await websocket.send_json({"type": "HEALTH_CHANGED", "data": health_data})

            while True:
                data = await websocket.receive_json()
                # Handle client ping / voice triggers over WS if needed
                if data.get("type") == "PING":
                    await websocket.send_json({"type": "PONG"})
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

        logger.info(f"API Command Received: '{req.input}'")
        await ws_manager.broadcast({"type": "BRAIN_STARTED", "input": req.input})

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
            status_val = tool_result.status.value if (tool_result and hasattr(tool_result.status, "value")) else "SUCCESS"

            response_payload = {
                "type": "BRAIN_COMPLETED",
                "request_id": req.request_id or f"req-{asyncio.get_event_loop().time()}",
                "status": status_val,
                "input": req.input,
                "response": response_text,
                "tool_used": tool_used,
                "widgetType": "ASSISTANT_RESPONSE",
                "widgetData": {
                    "tool_used": tool_used,
                    "execution_time_sec": exec_time,
                },
            }

            await ws_manager.broadcast(response_payload)

            # Auto TTS if voice manager is active
            if app.state.voice_manager and app.state.agent.config.voice_enabled:
                asyncio.create_task(asyncio.to_thread(app.state.voice_manager.speak, response_text))

            return response_payload

        except Exception as e:
            logger.error(f"Error processing command via API: {e}")
            err_payload = {"type": "ERROR_OCCURRED", "message": f"Error executing command: {str(e)}"}
            await ws_manager.broadcast(err_payload)
            raise HTTPException(status_code=500, detail=str(e))

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
        result = await asyncio.to_thread(app.state.voice_manager.listen_and_process, 4.0)
        await ws_manager.broadcast({"type": "VOICE_STATE_CHANGED", "state": "idle"})
        return {"status": "completed", "transcript": result}

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
