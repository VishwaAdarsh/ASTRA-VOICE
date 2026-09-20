"""
Test Suite for ASTRA Central Event Bus and Internal Event Architecture (Phase V2-09).
Covers event models, priority queue ordering, subscriber error isolation, backpressure,
adapters (UI, Health, Logging), and subsystem integration with AstraAgent and VoiceSession.
"""

import asyncio
import queue
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.brain.agent import AstraAgent
from src.brain.llm.models import DecisionType, LLMDecision
from src.brain.models import ExecutionStatus, ToolRequest, ToolResult
from src.core.config import Config
from src.core.events import (
    ASTRAEvent,
    AstraEventType,
    EventBus,
    EventPriority,
    HealthAdapter,
    LoggingAdapter,
    UIEventAdapter,
)
from src.core.health import HealthManager, HealthStatus
from src.voice.events import VoiceEvent
from src.voice.models import VoiceState
from src.voice.session import VoiceSession


# ============================================================================
# 1. Event Model & Sanitization Tests
# ============================================================================

def test_event_model_creation_and_defaults():
    """Verify default values and types on ASTRAEvent creation."""
    event = ASTRAEvent(
        event_type=AstraEventType.AGENT_STARTED,
        source="agent",
        payload={"input": "open notepad"},
    )
    assert event.event_id.startswith("evt-")
    assert event.event_type == AstraEventType.AGENT_STARTED
    assert event.source == "agent"
    assert event.priority == EventPriority.NORMAL
    assert event.timestamp > 0
    assert event.payload == {"input": "open notepad"}

    # Test serialization
    data = event.to_dict()
    assert data["event_type"] == "AGENT_STARTED"
    assert data["source"] == "agent"
    assert data["priority"] == "NORMAL"


def test_event_sanitization_secrets():
    """Verify API keys and tokens are redacted from event payloads."""
    event = ASTRAEvent(
        event_type=AstraEventType.AGENT_STARTED,
        source="agent",
        payload={
            "api_key": "AIzaSyD-1234567890abcdefghijklmnopqrst",
            "normal_field": "hello world",
        },
    )
    assert "[REDACTED" in event.payload.get("api_key", "")
    assert event.payload.get("normal_field") == "hello world"


def test_event_sanitization_audio_and_image():
    """Verify raw PCM audio buffers and large screenshot data are omitted."""
    raw_audio = b"\x00\x01" * 1000
    large_image = "data:image/png;base64," + "A" * 500

    event = ASTRAEvent(
        event_type=AstraEventType.VOICE_SPEECH_DETECTED,
        source="voice",
        payload={
            "audio_bytes": raw_audio,
            "raw_audio": raw_audio,
            "screenshot": large_image,
            "safe_metric": 42.0,
        },
    )
    assert "<omitted: audio buffer" in event.payload["audio_bytes"]
    assert "<omitted: audio buffer" in event.payload["raw_audio"]
    assert "<omitted: image data" in event.payload["screenshot"]
    assert event.payload["safe_metric"] == 42.0


def test_event_priority_ordering():
    """Verify PriorityQueue orders events by priority then timestamp."""
    pq = queue.PriorityQueue()

    e_low = ASTRAEvent(
        event_type=AstraEventType.AGENT_THINKING,
        source="agent",
        priority=EventPriority.LOW,
        timestamp=100.0,
    )
    e_critical = ASTRAEvent(
        event_type=AstraEventType.ACTION_BLOCKED,
        source="security",
        priority=EventPriority.CRITICAL,
        timestamp=200.0,
    )
    e_high = ASTRAEvent(
        event_type=AstraEventType.VOICE_INTERRUPTED,
        source="voice",
        priority=EventPriority.HIGH,
        timestamp=150.0,
    )
    e_normal = ASTRAEvent(
        event_type=AstraEventType.TOOL_STARTED,
        source="tool",
        priority=EventPriority.NORMAL,
        timestamp=50.0,
    )

    for e in [e_low, e_critical, e_high, e_normal]:
        pq.put(e)

    # Expected order: CRITICAL (0), HIGH (1), NORMAL (2), LOW (3)
    assert pq.get() == e_critical
    assert pq.get() == e_high
    assert pq.get() == e_normal
    assert pq.get() == e_low


# ============================================================================
# 2. EventBus Pub/Sub & Error Isolation Tests
# ============================================================================

def test_event_bus_subscribe_exact():
    """Verify exact event type subscriptions receive matching events."""
    bus = EventBus(start_worker=False)
    received = []

    def handler(event: ASTRAEvent):
        received.append(event)

    bus.subscribe(AstraEventType.VOICE_TRANSCRIBED, handler)

    e1 = ASTRAEvent(event_type=AstraEventType.VOICE_TRANSCRIBED, source="voice", payload={"text": "hello"})
    e2 = ASTRAEvent(event_type=AstraEventType.VOICE_SPEAKING_STARTED, source="voice")

    bus.publish_sync(e1)
    bus.publish_sync(e2)

    assert len(received) == 1
    assert received[0].event_type == AstraEventType.VOICE_TRANSCRIBED


def test_event_bus_subscribe_wildcard_all():
    """Verify global wildcard ('*') receives all published events."""
    bus = EventBus(start_worker=False)
    received = []

    bus.subscribe("*", lambda e: received.append(e))

    e1 = ASTRAEvent(event_type=AstraEventType.AGENT_STARTED, source="agent")
    e2 = ASTRAEvent(event_type=AstraEventType.TOOL_STARTED, source="tool")

    bus.publish_sync(e1)
    bus.publish_sync(e2)

    assert len(received) == 2


def test_event_bus_subscribe_wildcard_category():
    """Verify category wildcard ('VOICE_*') receives only matching category events."""
    bus = EventBus(start_worker=False)
    received = []

    bus.subscribe("VOICE_*", lambda e: received.append(e))

    e_voice1 = ASTRAEvent(event_type=AstraEventType.VOICE_SPEECH_DETECTED, source="voice")
    e_voice2 = ASTRAEvent(event_type=AstraEventType.VOICE_SPEAKING_STOPPED, source="voice")
    e_agent = ASTRAEvent(event_type=AstraEventType.AGENT_STARTED, source="agent")

    bus.publish_sync(e_voice1)
    bus.publish_sync(e_agent)
    bus.publish_sync(e_voice2)

    assert len(received) == 2
    assert all(e.event_type.value.startswith("VOICE_") for e in received)


def test_event_bus_unsubscribe():
    """Verify unregistering a subscriber callback removes it cleanly."""
    bus = EventBus(start_worker=False)
    received = []

    def handler(event: ASTRAEvent):
        received.append(event)

    bus.subscribe(AstraEventType.TOOL_STARTED, handler)
    e = ASTRAEvent(event_type=AstraEventType.TOOL_STARTED, source="tool")

    bus.publish_sync(e)
    assert len(received) == 1

    removed = bus.unsubscribe(AstraEventType.TOOL_STARTED, handler)
    assert removed is True

    bus.publish_sync(e)
    assert len(received) == 1


def test_event_bus_subscriber_error_isolation():
    """Verify an exception in one subscriber does not crash the bus or prevent other subscribers."""
    bus = EventBus(start_worker=False)
    received = []

    def failing_handler(event: ASTRAEvent):
        raise RuntimeError("Subscriber explosion!")

    def healthy_handler(event: ASTRAEvent):
        received.append(event)

    bus.subscribe(AstraEventType.AGENT_COMPLETED, failing_handler)
    bus.subscribe(AstraEventType.AGENT_COMPLETED, healthy_handler)

    e = ASTRAEvent(event_type=AstraEventType.AGENT_COMPLETED, source="agent")
    # Should not raise exception
    bus.publish_sync(e)

    assert len(received) == 1
    assert received[0] == e


# ============================================================================
# 3. Asynchronous Worker, Backpressure & Lifecycle Tests
# ============================================================================

def test_event_bus_async_worker():
    """Verify asynchronous dispatch via the background worker thread."""
    bus = EventBus(start_worker=True)
    received = []
    received_event = threading.Event()

    def handler(event: ASTRAEvent):
        received.append(event)
        received_event.set()

    bus.subscribe(AstraEventType.AGENT_STARTED, handler)

    event = ASTRAEvent(event_type=AstraEventType.AGENT_STARTED, source="agent")
    enqueued = bus.publish(event)
    assert enqueued is True

    assert received_event.wait(timeout=2.0)
    assert len(received) == 1

    bus.stop()


def test_event_bus_backpressure_drop_low_priority():
    """Verify queue capacity limits drop LOW priority events when full."""
    bus = EventBus(max_queue_size=2, start_worker=False)

    e1 = ASTRAEvent(event_type=AstraEventType.AGENT_THINKING, source="agent", priority=EventPriority.NORMAL)
    e2 = ASTRAEvent(event_type=AstraEventType.AGENT_THINKING, source="agent", priority=EventPriority.NORMAL)
    e3_low = ASTRAEvent(event_type=AstraEventType.AGENT_THINKING, source="agent", priority=EventPriority.LOW)

    assert bus.publish(e1) is True
    assert bus.publish(e2) is True
    # 3rd event should be dropped due to queue being full
    assert bus.publish(e3_low) is False

    metrics = bus.get_metrics()
    assert metrics["total_dropped"] == 1


def test_event_bus_backpressure_preserve_critical():
    """Verify CRITICAL events evict lower-priority events to avoid being dropped."""
    bus = EventBus(max_queue_size=2, start_worker=False)

    e_low1 = ASTRAEvent(event_type=AstraEventType.AGENT_THINKING, source="agent", priority=EventPriority.LOW)
    e_low2 = ASTRAEvent(event_type=AstraEventType.AGENT_THINKING, source="agent", priority=EventPriority.LOW)
    e_crit = ASTRAEvent(event_type=AstraEventType.ACTION_BLOCKED, source="security", priority=EventPriority.CRITICAL)

    assert bus.publish(e_low1) is True
    assert bus.publish(e_low2) is True
    # Critical event should succeed by making room
    assert bus.publish(e_crit) is True


def test_event_bus_clean_shutdown():
    """Verify EventBus worker thread shuts down cleanly."""
    bus = EventBus(start_worker=True)
    assert bus._running is True
    assert bus._worker_thread.is_alive()

    bus.stop(drain=True)
    assert bus._running is False
    assert not bus._worker_thread.is_alive()


def test_event_bus_metrics():
    """Verify operational metrics reporting."""
    bus = EventBus(max_queue_size=500, start_worker=False)
    bus.subscribe(AstraEventType.TOOL_STARTED, lambda e: None)
    bus.subscribe("VOICE_*", lambda e: None)

    bus.publish_sync(ASTRAEvent(event_type=AstraEventType.TOOL_STARTED, source="tool"))

    metrics = bus.get_metrics()
    assert metrics["max_queue_size"] == 500
    assert metrics["total_published"] == 1
    assert metrics["total_dispatched"] == 1
    assert metrics["active_subscriber_registrations"] == 2


# ============================================================================
# 4. Adapters Tests (UI, Health, Logging)
# ============================================================================

def test_ui_adapter_websocket_forwarding():
    """Verify UIEventAdapter forwards UI-relevant events to WebSocket manager."""
    async def _run():
        mock_ws = MagicMock()
        mock_ws.broadcast = AsyncMock()

        bus = EventBus(sync_mode=True)
        loop = asyncio.get_running_loop()
        adapter = UIEventAdapter(ws_manager=mock_ws, event_bus=bus, loop=loop)

        event = ASTRAEvent(
            event_type=AstraEventType.AGENT_COMPLETED,
            source="agent",
            request_id="req-test-1",
            payload={"response": "Task finished."},
        )

        bus.publish_sync(event)
        await asyncio.sleep(0.05)  # Yield for task execution

        mock_ws.broadcast.assert_called_once()
        call_args = mock_ws.broadcast.call_args
        assert call_args[0][0] == "AGENT_COMPLETED"
        assert call_args[1]["request_id"] == "req-test-1"
        assert call_args[0][1]["response"] == "Task finished."

        adapter.unregister()

    asyncio.run(_run())


def test_health_adapter_voice_and_agent_errors():
    """Verify HealthAdapter updates HealthManager upon receiving failure events."""
    health_mgr = HealthManager()
    bus = EventBus(sync_mode=True)
    adapter = HealthAdapter(health_manager=health_mgr, event_bus=bus)

    # 1. Voice Error
    e_voice = ASTRAEvent(
        event_type=AstraEventType.VOICE_ERROR,
        source="voice",
        payload={"error": "Microphone disconnected"},
    )
    bus.publish_sync(e_voice)
    assert health_mgr.get_status("voice").status == HealthStatus.DEGRADED
    assert "Microphone disconnected" in health_mgr.get_status("voice").message

    # 2. Agent Failure
    e_agent = ASTRAEvent(
        event_type=AstraEventType.AGENT_FAILED,
        source="agent",
        payload={"error": "LLM timeout"},
    )
    bus.publish_sync(e_agent)
    assert health_mgr.get_status("agent").status == HealthStatus.DEGRADED

    # 3. Tool Failure
    e_tool = ASTRAEvent(
        event_type=AstraEventType.TOOL_FAILED,
        source="tool",
        payload={"tool": "open_application", "error": "App not found"},
    )
    bus.publish_sync(e_tool)
    assert health_mgr.get_status("tools").status == HealthStatus.DEGRADED

    # 4. Runtime Error
    e_runtime = ASTRAEvent(
        event_type=AstraEventType.RUNTIME_ERROR,
        source="runtime",
        payload={"error": "Out of memory"},
    )
    bus.publish_sync(e_runtime)
    assert health_mgr.get_status("system").status == HealthStatus.UNAVAILABLE

    adapter.unregister()


def test_logging_adapter():
    """Verify LoggingAdapter processes events across all priority levels without errors."""
    bus = EventBus(start_worker=False)
    adapter = LoggingAdapter(event_bus=bus)

    for priority in [EventPriority.CRITICAL, EventPriority.HIGH, EventPriority.NORMAL, EventPriority.LOW]:
        e = ASTRAEvent(
            event_type=AstraEventType.AGENT_STARTED,
            source="agent",
            priority=priority,
            payload={"step": priority.name},
        )
        bus.publish_sync(e)

    adapter.unregister()


# ============================================================================
# 5. Subsystem Integration Tests (AstraAgent & VoiceSession)
# ============================================================================

def test_agent_publishes_lifecycle_events():
    """Verify AstraAgent publishes AGENT_STARTED and AGENT_COMPLETED events with request_id."""
    bus = EventBus(sync_mode=True)
    received_events = []

    bus.subscribe("AGENT_*", lambda e: received_events.append(e))

    agent = AstraAgent(event_bus=bus)
    # Mock LLM client to return conversational response immediately
    agent.llm_client.generate_decision = MagicMock(
        return_value=LLMDecision(decision_type=DecisionType.RESPONSE, message="Hello there!")
    )

    response, result = agent.process_command("hello", request_id="req-agent-1")
    assert response == "Hello there!"
    assert result.status == ExecutionStatus.SUCCESS

    event_types = [e.event_type for e in received_events]
    assert AstraEventType.AGENT_STARTED in event_types
    assert AstraEventType.AGENT_THINKING in event_types
    assert AstraEventType.AGENT_COMPLETED in event_types

    completed_event = next(e for e in received_events if e.event_type == AstraEventType.AGENT_COMPLETED)
    assert completed_event.request_id == "req-agent-1"
    assert completed_event.payload["response"] == "Hello there!"


def test_agent_publishes_tool_events():
    """Verify AstraAgent publishes TOOL_STARTED and TOOL_COMPLETED events."""
    bus = EventBus(sync_mode=True)
    received_events = []

    bus.subscribe("TOOL_*", lambda e: received_events.append(e))

    agent = AstraAgent(event_bus=bus)

    # First iteration: tool call; Second iteration: response
    agent.llm_client.generate_decision = MagicMock(
        side_effect=[
            LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="system_information",
                arguments={},
            ),
            LLMDecision(
                decision_type=DecisionType.RESPONSE,
                message="System info retrieved.",
            ),
        ]
    )

    agent.process_command("check system info", request_id="req-tool-1")

    event_types = [e.event_type for e in received_events]
    assert AstraEventType.TOOL_STARTED in event_types
    assert AstraEventType.TOOL_COMPLETED in event_types

    tool_started = next(e for e in received_events if e.event_type == AstraEventType.TOOL_STARTED)
    assert tool_started.request_id == "req-tool-1"
    assert tool_started.payload["tool"] == "system_information"


def test_voice_session_publishes_voice_events():
    """Verify VoiceSession state changes and emit_event publish to EventBus."""
    bus = EventBus(sync_mode=True)
    received_events = []

    bus.subscribe("VOICE_*", lambda e: received_events.append(e))
    bus.subscribe(AstraEventType.WAKE_WORD_DETECTED, lambda e: received_events.append(e))

    mock_agent = MagicMock()
    mock_mic = MagicMock()
    mock_mic.config = MagicMock()
    mock_stt = MagicMock()
    mock_tts = MagicMock()

    session = VoiceSession(
        agent=mock_agent,
        microphone_manager=mock_mic,
        stt_provider=mock_stt,
        tts_provider=mock_tts,
        event_bus=bus,
    )

    # 1. State change
    session._set_state(VoiceState.LISTENING)

    # 2. Domain event
    session.emit_event(VoiceEvent.WAKE_WORD_DETECTED, {"keyword": "hey astra"})

    # 3. Interruption event
    session.emit_event(VoiceEvent.VOICE_INTERRUPTED)

    event_types = [e.event_type for e in received_events]
    assert AstraEventType.VOICE_LISTENING_STARTED in event_types
    assert AstraEventType.WAKE_WORD_DETECTED in event_types
    assert AstraEventType.VOICE_INTERRUPTED in event_types

    wake_event = next(e for e in received_events if e.event_type == AstraEventType.WAKE_WORD_DETECTED)
    assert wake_event.payload["keyword"] == "hey astra"


def test_thread_safety_concurrent_publishes():
    """Verify thread-safety when multiple threads publish simultaneously to EventBus."""
    bus = EventBus(start_worker=True)
    received_count = 0
    lock = threading.Lock()

    def count_handler(event: ASTRAEvent):
        nonlocal received_count
        with lock:
            received_count += 1

    bus.subscribe("*", count_handler)

    num_threads = 10
    events_per_thread = 20

    def publisher(thread_id: int):
        for i in range(events_per_thread):
            bus.publish(
                ASTRAEvent(
                    event_type=AstraEventType.AGENT_THINKING,
                    source=f"thread-{thread_id}",
                    payload={"index": i},
                )
            )

    threads = [threading.Thread(target=publisher, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    bus.drain(timeout=3.0)
    bus.stop()

    assert received_count == num_threads * events_per_thread
