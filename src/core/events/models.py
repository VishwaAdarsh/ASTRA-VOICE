"""
ASTRA Central Event Models and Types.
Defines the canonical event schema, priority tiers, and standardized event taxonomy.
"""

from dataclasses import dataclass, field
from enum import Enum, IntEnum
import json
import time
from typing import Any, Optional
import uuid

from src.security.auditor import SecretRedactionFilter


class EventPriority(IntEnum):
    """
    Priority tiers for the Central Event Bus.
    Lower numerical values indicate higher processing priority in the queue.
    """
    CRITICAL = 0  # Security blocks, runtime crashes, critical errors
    HIGH = 1      # Voice interrupts, user cancellation, permission prompts
    NORMAL = 2    # Standard command, agent, tool, and task transitions
    LOW = 3       # Diagnostic metrics, background telemetry, verbose logs


class AstraEventType(str, Enum):
    """Standardized event taxonomy for the ASTRA ecosystem."""

    # Voice Subsystem
    VOICE_SESSION_STARTED = "VOICE_SESSION_STARTED"
    VOICE_SESSION_ENDED = "VOICE_SESSION_ENDED"
    VOICE_LISTENING_STARTED = "VOICE_LISTENING_STARTED"
    VOICE_SPEECH_DETECTED = "VOICE_SPEECH_DETECTED"
    VOICE_CAPTURING_STARTED = "VOICE_CAPTURING_STARTED"
    VOICE_SPEECH_ENDED = "VOICE_SPEECH_ENDED"
    VOICE_TRANSCRIBING = "VOICE_TRANSCRIBING"
    VOICE_TRANSCRIBED = "VOICE_TRANSCRIBED"
    VOICE_SPEAKING_STARTED = "VOICE_SPEAKING_STARTED"
    VOICE_SPEAKING_STOPPED = "VOICE_SPEAKING_STOPPED"
    VOICE_INTERRUPTED = "VOICE_INTERRUPTED"
    VOICE_ERROR = "VOICE_ERROR"
    WAKE_WORD_DETECTED = "WAKE_WORD_DETECTED"
    BARGE_IN_DETECTED = "BARGE_IN_DETECTED"

    # Agent Subsystem
    AGENT_STARTED = "AGENT_STARTED"
    AGENT_THINKING = "AGENT_THINKING"
    AGENT_COMPLETED = "AGENT_COMPLETED"
    AGENT_FAILED = "AGENT_FAILED"
    AGENT_CLARIFICATION_REQUESTED = "AGENT_CLARIFICATION_REQUESTED"

    # Tool Subsystem
    TOOL_STARTED = "TOOL_STARTED"
    TOOL_COMPLETED = "TOOL_COMPLETED"
    TOOL_FAILED = "TOOL_FAILED"

    # Runtime Subsystem
    RUNTIME_STARTED = "RUNTIME_STARTED"
    RUNTIME_READY = "RUNTIME_READY"
    RUNTIME_STOPPING = "RUNTIME_STOPPING"
    RUNTIME_STOPPED = "RUNTIME_STOPPED"
    RUNTIME_ERROR = "RUNTIME_ERROR"

    # Task & Automation Subsystems
    TASK_CREATED = "TASK_CREATED"
    TASK_STARTED = "TASK_STARTED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_FAILED = "TASK_FAILED"
    AUTOMATION_TRIGGERED = "AUTOMATION_TRIGGERED"
    AUTOMATION_COMPLETED = "AUTOMATION_COMPLETED"
    AUTOMATION_FAILED = "AUTOMATION_FAILED"

    # Security Subsystem
    PERMISSION_REQUESTED = "PERMISSION_REQUESTED"
    CONFIRMATION_REQUESTED = "CONFIRMATION_REQUESTED"
    ACTION_BLOCKED = "ACTION_BLOCKED"

    # Health Subsystem
    HEALTH_CHANGED = "HEALTH_CHANGED"

    # Capability Subsystem (Phase V2-10)
    CAPABILITY_REGISTERED = "CAPABILITY_REGISTERED"
    CAPABILITY_ENABLED = "CAPABILITY_ENABLED"
    CAPABILITY_DISABLED = "CAPABILITY_DISABLED"
    CAPABILITY_AVAILABILITY_CHANGED = "CAPABILITY_AVAILABILITY_CHANGED"
    CAPABILITY_HEALTH_CHANGED = "CAPABILITY_HEALTH_CHANGED"
    CAPABILITY_RESOLUTION_FAILED = "CAPABILITY_RESOLUTION_FAILED"
    CAPABILITY_VALIDATION_FAILED = "CAPABILITY_VALIDATION_FAILED"
    CAPABILITY_EXECUTION_STARTED = "CAPABILITY_EXECUTION_STARTED"
    CAPABILITY_EXECUTION_COMPLETED = "CAPABILITY_EXECUTION_COMPLETED"
    CAPABILITY_EXECUTION_FAILED = "CAPABILITY_EXECUTION_FAILED"

    # Memory Subsystem (Phase V2-11)
    MEMORY_CREATED = "MEMORY_CREATED"
    MEMORY_UPDATED = "MEMORY_UPDATED"
    MEMORY_CONFIRMED = "MEMORY_CONFIRMED"
    MEMORY_SUPERSEDED = "MEMORY_SUPERSEDED"
    MEMORY_EXPIRED = "MEMORY_EXPIRED"
    MEMORY_REVOKED = "MEMORY_REVOKED"
    MEMORY_RETRIEVAL_FAILED = "MEMORY_RETRIEVAL_FAILED"


def _sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize an event payload:
    1. Redact API keys, tokens, and secrets using SecretRedactionFilter.
    2. Strip raw binary audio data and excessively large image/screenshot payloads.
    """
    if not isinstance(payload, dict):
        return {}

    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        # Prevent transmitting raw audio buffers
        if any(k in key.lower() for k in ("audio_bytes", "audio_buffer", "raw_audio", "pcm_data")):
            sanitized[key] = f"<omitted: audio buffer ({type(value).__name__})>"
            continue

        # Prevent transmitting huge screenshot base64 strings
        if any(k in key.lower() for k in ("screenshot", "image_base64", "screen_buffer")):
            if isinstance(value, str) and len(value) > 200:
                sanitized[key] = f"<omitted: image data ({len(value)} chars)>"
                continue
            elif isinstance(value, (bytes, bytearray)):
                sanitized[key] = f"<omitted: binary image data ({len(value)} bytes)>"
                continue

        # Strip binary bytes in general
        if isinstance(value, (bytes, bytearray)):
            sanitized[key] = f"<omitted: binary data ({len(value)} bytes)>"
            continue

        sanitized[key] = value

    # Apply secret redaction across the payload
    try:
        json_str = json.dumps(sanitized, default=str)
        redacted_str = SecretRedactionFilter.redact(json_str)
        return json.loads(redacted_str)
    except Exception:
        return sanitized


@dataclass
class ASTRAEvent:
    """
    Canonical Event Representation in ASTRA.
    Events represent state transitions or notifications ("X happened"), never commands.
    """
    event_type: AstraEventType | str
    source: str
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: f"evt-{uuid.uuid4().hex[:12]}")
    timestamp: float = field(default_factory=time.time)
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    priority: EventPriority = EventPriority.NORMAL
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Normalize event_type if string passed
        if isinstance(self.event_type, str):
            try:
                self.event_type = AstraEventType(self.event_type)
            except ValueError:
                pass  # Allow custom/extension event types if needed

        # Sanitize payload on creation
        self.payload = _sanitize_payload(self.payload)

    def __lt__(self, other: "ASTRAEvent") -> bool:
        """Comparison for PriorityQueue ordering: lower priority value first, then earliest timestamp."""
        if not isinstance(other, ASTRAEvent):
            return NotImplemented
        return (self.priority, self.timestamp) < (other.priority, other.timestamp)

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to a standard dictionary representation."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value if isinstance(self.event_type, AstraEventType) else str(self.event_type),
            "source": self.source,
            "timestamp": self.timestamp,
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "priority": self.priority.name,
            "payload": self.payload,
            "metadata": self.metadata,
        }
