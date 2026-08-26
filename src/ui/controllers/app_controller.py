"""
AppController - Bridge between ASTRA Core/Voice Subsystem and PySide6 UI.
Executes long-running core tasks in background worker threads and emits Qt Signals.
Zero business logic resides in UI widgets.
"""

from typing import TYPE_CHECKING
from PySide6.QtCore import QObject, QThread, Signal
from src.brain.models import ToolResult
from src.core.logger import get_logger
from src.voice.events import VoiceEvent
from src.voice.manager import VoiceManager
from src.voice.models import VoiceState

if TYPE_CHECKING:
    from src.brain.agent import AstraAgent

logger = get_logger()


class TextCommandWorker(QThread):
    """Background worker thread for processing text commands without blocking Qt GUI loop."""

    finished_signal = Signal(str, object)  # (response_text, ToolResult)

    def __init__(self, agent: "AstraAgent", command_text: str):
        super().__init__()
        self.agent = agent
        self.command_text = command_text

    def run(self):
        try:
            response_text, result = self.agent.process_command(self.command_text)
            self.finished_signal.emit(response_text, result)
        except Exception as e:
            logger.error(f"Error in TextCommandWorker: {e}")
            self.finished_signal.emit(f"Error: {e}", None)


class VoiceTurnWorker(QThread):
    """Background worker thread for executing a single voice turn."""

    finished_signal = Signal(str, object)

    def __init__(self, voice_manager: VoiceManager):
        super().__init__()
        self.voice_manager = voice_manager

    def run(self):
        try:
            response_text, result = self.voice_manager.listen_and_process(duration_seconds=3.0)
            self.finished_signal.emit(response_text, result)
        except Exception as e:
            logger.error(f"Error in VoiceTurnWorker: {e}")
            self.finished_signal.emit(f"Voice error: {e}", None)


class AppController(QObject):
    """Bridge controller emitting Qt signals to widgets."""

    sig_command_received = Signal(str)
    sig_response_ready = Signal(str, object)  # (response_text, ToolResult)
    sig_voice_state_changed = Signal(str)     # VoiceState string
    sig_activity_logged = Signal(dict)        # Activity record payload
    sig_notification = Signal(str, str)       # (level, message)

    def __init__(self, agent: "AstraAgent", voice_manager: VoiceManager):
        super().__init__()
        self.agent = agent
        self.voice_manager = voice_manager
        self.activity_history: list[dict] = []

        # Hook into voice event listener
        self.voice_manager.session.event_listener = self._on_voice_event

    def _on_voice_event(self, event: VoiceEvent, payload: dict) -> None:
        """Callback handling internal voice events."""
        if "new_state" in payload:
            state_val = payload["new_state"]
            state_str = state_val.value if hasattr(state_val, "value") else str(state_val)
            self.sig_voice_state_changed.emit(state_str)
        elif event == VoiceEvent.VOICE_ERROR:
            err = payload.get("error", "Unknown voice error")
            self.sig_notification.emit("ERROR", err)


    def submit_text_command(self, text: str) -> None:
        """Submit user text command for background processing."""
        if not text or not text.strip():
            return

        cleaned = text.strip()
        self.sig_command_received.emit(cleaned)

        # Log activity start
        activity_entry = {
            "type": "COMMAND",
            "command": cleaned,
            "status": "PROCESSING",
            "timestamp": QThread.currentThread().objectName() or "Now",
        }
        self.activity_history.append(activity_entry)
        self.sig_activity_logged.emit(activity_entry)

        # Launch non-blocking worker thread
        self.worker = TextCommandWorker(self.agent, cleaned)
        self.worker.finished_signal.connect(self._on_command_finished)
        self.worker.start()

    def trigger_voice_turn(self) -> None:
        """Trigger a voice turn interaction in a background thread."""

        if self.voice_manager.state != VoiceState.IDLE:
            self.voice_manager.stop_speaking()
            return

        self.voice_worker = VoiceTurnWorker(self.voice_manager)
        self.voice_worker.finished_signal.connect(self._on_command_finished)
        self.voice_worker.start()

    def _on_command_finished(self, response_text: str, result: ToolResult | None) -> None:
        """Handle completion of command execution from background thread."""
        status = result.status.value if result else "SUCCESS"
        activity_entry = {
            "type": "RESPONSE",
            "response": response_text,
            "status": status,
            "tool_name": result.data.get("app_name") if result and result.data else None,
        }
        self.activity_history.append(activity_entry)
        self.sig_activity_logged.emit(activity_entry)

        self.sig_response_ready.emit(response_text, result)
