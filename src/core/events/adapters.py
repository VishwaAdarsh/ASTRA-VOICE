"""
ASTRA Subsystem Event Adapters.
Bridges the Central Event Bus to UI WebSockets, System Health, and Structured Logging.
"""

import asyncio
from typing import Any, Optional

from src.core.events.bus import EventBus
from src.core.events.models import ASTRAEvent, AstraEventType, EventPriority
from src.core.health import HealthManager, HealthStatus
from src.core.logger import get_logger

logger = get_logger()


class UIEventAdapter:
    """
    Bridges internal ASTRA EventBus events to the React UI via WebSocketManager.
    Translates internal event schemas to frontend WebSocket contracts without
    direct coupling between subsystems and WebSocket networking.
    """

    UI_EVENT_TYPES = {
        # Voice events
        AstraEventType.VOICE_SESSION_STARTED.value,
        AstraEventType.VOICE_SESSION_ENDED.value,
        AstraEventType.VOICE_LISTENING_STARTED.value,
        AstraEventType.VOICE_SPEECH_DETECTED.value,
        AstraEventType.VOICE_CAPTURING_STARTED.value,
        AstraEventType.VOICE_SPEECH_ENDED.value,
        AstraEventType.VOICE_TRANSCRIBING.value,
        AstraEventType.VOICE_TRANSCRIBED.value,
        AstraEventType.VOICE_SPEAKING_STARTED.value,
        AstraEventType.VOICE_SPEAKING_STOPPED.value,
        AstraEventType.VOICE_INTERRUPTED.value,
        AstraEventType.VOICE_ERROR.value,
        AstraEventType.WAKE_WORD_DETECTED.value,
        AstraEventType.BARGE_IN_DETECTED.value,
        # Agent & Tool events
        AstraEventType.AGENT_STARTED.value,
        AstraEventType.AGENT_THINKING.value,
        AstraEventType.AGENT_COMPLETED.value,
        AstraEventType.AGENT_FAILED.value,
        AstraEventType.AGENT_CLARIFICATION_REQUESTED.value,
        AstraEventType.TOOL_STARTED.value,
        AstraEventType.TOOL_COMPLETED.value,
        AstraEventType.TOOL_FAILED.value,
        # Task & Automation events
        AstraEventType.TASK_CREATED.value,
        AstraEventType.TASK_STARTED.value,
        AstraEventType.TASK_COMPLETED.value,
        AstraEventType.TASK_FAILED.value,
        AstraEventType.AUTOMATION_TRIGGERED.value,
        AstraEventType.AUTOMATION_COMPLETED.value,
        AstraEventType.AUTOMATION_FAILED.value,
        # Security & Health events
        AstraEventType.PERMISSION_REQUESTED.value,
        AstraEventType.CONFIRMATION_REQUESTED.value,
        AstraEventType.ACTION_BLOCKED.value,
        AstraEventType.HEALTH_CHANGED.value,
        # Runtime
        AstraEventType.RUNTIME_STARTED.value,
        AstraEventType.RUNTIME_READY.value,
        AstraEventType.RUNTIME_STOPPING.value,
        AstraEventType.RUNTIME_STOPPED.value,
        AstraEventType.RUNTIME_ERROR.value,
    }

    def __init__(
        self,
        ws_manager: Any,
        event_bus: EventBus,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ):
        self.ws_manager = ws_manager
        self.event_bus = event_bus
        self.loop = loop
        self._registered = False
        self.register()

    def register(self) -> None:
        """Subscribe to the Event Bus for all UI-relevant events."""
        if not self._registered:
            self.event_bus.subscribe("*", self.handle_event)
            self._registered = True

    def unregister(self) -> None:
        """Unsubscribe from the Event Bus."""
        if self._registered:
            self.event_bus.unsubscribe("*", self.handle_event)
            self._registered = False

    def handle_event(self, event: ASTRAEvent) -> None:
        """Process an internal event and broadcast to connected UI clients if relevant."""
        event_type_str = (
            event.event_type.value
            if isinstance(event.event_type, AstraEventType)
            else str(event.event_type)
        )

        if event_type_str not in self.UI_EVENT_TYPES:
            return

        # Prepare payload for UI WebSocket envelope
        ui_payload = {
            "type": event_type_str,
            "event_id": event.event_id,
            "timestamp": event.timestamp,
            "request_id": event.request_id,
            "source": event.source,
            "priority": event.priority.name,
            **event.payload,
        }

        self._broadcast_to_ui(event_type_str, ui_payload, event.request_id)

    def _broadcast_to_ui(
        self,
        event_type: str,
        payload: dict[str, Any],
        request_id: Optional[str] = None,
    ) -> None:
        """Safely broadcast to WebSocket clients across thread/coroutine boundaries."""
        if not self.ws_manager:
            return

        try:
            current_loop = None
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

            target_loop = self.loop or current_loop

            if target_loop and target_loop.is_running():
                if current_loop == target_loop:
                    # Already on the event loop thread
                    asyncio.create_task(
                        self.ws_manager.broadcast(event_type, payload, request_id=request_id)
                    )
                else:
                    # Called from worker/background thread
                    asyncio.run_coroutine_threadsafe(
                        self.ws_manager.broadcast(event_type, payload, request_id=request_id),
                        target_loop,
                    )
            else:
                logger.debug("No active asyncio event loop available for UI broadcast.")
        except Exception as e:
            logger.warning(f"UIEventAdapter failed to broadcast event '{event_type}': {e}")


class HealthAdapter:
    """
    Subscribes to system failure and health events to update the HealthManager.
    """

    def __init__(self, health_manager: HealthManager, event_bus: EventBus):
        self.health_manager = health_manager
        self.event_bus = event_bus
        self._registered = False
        self.register()

    def register(self) -> None:
        if not self._registered:
            self.event_bus.subscribe(AstraEventType.VOICE_ERROR, self._on_voice_error)
            self.event_bus.subscribe(AstraEventType.AGENT_FAILED, self._on_agent_failed)
            self.event_bus.subscribe(AstraEventType.TOOL_FAILED, self._on_tool_failed)
            self.event_bus.subscribe(AstraEventType.RUNTIME_ERROR, self._on_runtime_error)
            self.event_bus.subscribe(AstraEventType.RUNTIME_READY, self._on_runtime_ready)
            self._registered = True

    def unregister(self) -> None:
        if self._registered:
            self.event_bus.unsubscribe(AstraEventType.VOICE_ERROR, self._on_voice_error)
            self.event_bus.unsubscribe(AstraEventType.AGENT_FAILED, self._on_agent_failed)
            self.event_bus.unsubscribe(AstraEventType.TOOL_FAILED, self._on_tool_failed)
            self.event_bus.unsubscribe(AstraEventType.RUNTIME_ERROR, self._on_runtime_error)
            self.event_bus.unsubscribe(AstraEventType.RUNTIME_READY, self._on_runtime_ready)
            self._registered = False

    def _on_voice_error(self, event: ASTRAEvent) -> None:
        msg = event.payload.get("error", "Voice error occurred")
        self.health_manager.set_status("voice", HealthStatus.DEGRADED, str(msg))

    def _on_agent_failed(self, event: ASTRAEvent) -> None:
        msg = event.payload.get("error", "Agent task failed")
        self.health_manager.set_status("agent", HealthStatus.DEGRADED, str(msg))

    def _on_tool_failed(self, event: ASTRAEvent) -> None:
        tool_name = event.payload.get("tool", "unknown_tool")
        error_msg = event.payload.get("error", "Tool execution failed")
        self.health_manager.set_status("tools", HealthStatus.DEGRADED, f"{tool_name}: {error_msg}")

    def _on_runtime_error(self, event: ASTRAEvent) -> None:
        msg = event.payload.get("error", "Runtime failure")
        self.health_manager.set_status("system", HealthStatus.UNAVAILABLE, str(msg))

    def _on_runtime_ready(self, event: ASTRAEvent) -> None:
        self.health_manager.set_status("system", HealthStatus.HEALTHY, "System ready")


class LoggingAdapter:
    """
    Subscribes to all events and produces structured diagnostic logs based on priority.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._registered = False
        self.register()

    def register(self) -> None:
        if not self._registered:
            self.event_bus.subscribe("*", self.handle_event)
            self._registered = True

    def unregister(self) -> None:
        if self._registered:
            self.event_bus.unsubscribe("*", self.handle_event)
            self._registered = False

    def handle_event(self, event: ASTRAEvent) -> None:
        event_type_str = (
            event.event_type.value
            if isinstance(event.event_type, AstraEventType)
            else str(event.event_type)
        )
        req_info = f" [req:{event.request_id}]" if event.request_id else ""
        msg = f"[EVENT] {event.source.upper()} -> {event_type_str}{req_info} (priority={event.priority.name})"

        if event.priority == EventPriority.CRITICAL:
            logger.critical(f"{msg} | payload={event.payload}")
        elif event.priority == EventPriority.HIGH:
            logger.warning(f"{msg} | payload={event.payload}")
        elif event.priority == EventPriority.NORMAL:
            logger.info(f"{msg}")
        else:
            logger.debug(f"{msg} | payload={event.payload}")
