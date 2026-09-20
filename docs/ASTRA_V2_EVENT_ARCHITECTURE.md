# ASTRA V2 — Central Event Bus & Internal Event Architecture

## 1. Overview & Purpose

Phase V2-09 establishes a centralized, thread-safe, decoupled internal **Event Bus** for the Python ASTRA runtime.

Prior to V2-09, subsystems communicated via direct method invocations or scattered callback mechanisms. The Central Event Bus decouples these subsystems:
- **Voice** announces speech detection, transcription, wake-word, and interruption events.
- **Agent** announces cognitive iterations, tool requests, and completion/failure.
- **Tools** announce execution start, completion, and failures.
- **Adapters** observe these events and bridge them to WebSockets (for the React UI), `HealthManager`, and structured diagnostic logs.

```
+-------------------------------------------------------------------------+
|                              ASTRA RUNTIME                              |
|                                                                         |
|  +----------------+     +------------------+     +-------------------+  |
|  | Voice Subsystem|     |  Agent Subsystem |     |  Tool Subsystem   |  |
|  +-------+--------+     +--------+---------+     +---------+---------+  |
|          |                       |                         |            |
|          +-----------------------+-------------------------+            |
|                                  |                                      |
|                                  v                                      |
|                 +---------------------------------+                     |
|                 |        Central Event Bus        |                     |
|                 |  - Priority Queue (Bounded)     |                     |
|                 |  - Daemon Worker Thread         |                     |
|                 |  - Subscriber Error Isolation   |                     |
|                 +----------------+----------------+                     |
|                                  |                                      |
|          +-----------------------+-------------------------+            |
|          |                       |                         |            |
|          v                       v                         v            |
|  +---------------+      +-----------------+       +------------------+  |
|  | UIEventAdapter|      |  HealthAdapter  |       |  LoggingAdapter  |  |
|  +-------+-------+      +--------+--------+       +------------------+  |
|          |                       |                                      |
|          v                       v                                      |
|     WebSocket               HealthManager                               |
|   (React Stitch)                                                        |
+-------------------------------------------------------------------------+
```

---

## 2. Core Architectural Principles

### 2.1 Events vs. Commands
- **Commands ("Please do X")**: Direct, authoritative instructions routed to specific executors (`AstraAgent.process_command`, `ToolExecutor.execute`). Commands require validation, permission checks, and return explicit results.
- **Events ("X happened")**: Informational broadcasts of past occurrences published to the Event Bus. Events cannot trigger arbitrary tool execution or bypass security gates.

### 2.2 Security & Data Hygiene
- **No Secrets**: All event payloads are sanitized using `SecretRedactionFilter` to prevent API keys or credentials from entering logs or UI WebSocket streams.
- **No Heavy Buffers**: Raw PCM audio arrays and full base64 screenshots are omitted from event payloads to prevent memory bloat and UI performance degradation.

### 2.3 Reliability & Isolation
- **Subscriber Error Isolation**: An unhandled exception in one subscriber callback is logged and trapped; it never crashes the Event Bus or prevents other subscribers from receiving the event.
- **Bounded Backpressure**: The queue has a bounded capacity (`max_queue_size=1000`). If the queue fills up, `LOW` and `NORMAL` priority events are dropped with warnings, while `HIGH` and `CRITICAL` events are protected.

---

## 3. Event Schema & Priority Model

### 3.1 Event Priority (`EventPriority`)

| Priority | Value | Use Cases | Backpressure Policy |
| :--- | :--- | :--- | :--- |
| `CRITICAL` | `0` | Security violations, runtime crashes, critical system faults | Never dropped; evicts lower-priority items |
| `HIGH` | `1` | Voice interruptions, barge-in, user cancellations, permission alerts | Protected; evicts lower-priority items |
| `NORMAL` | `2` | Agent thinking, tool execution, state transitions | Dropped when queue is full |
| `LOW` | `3` | Background telemetry, verbose diagnostic metrics | Dropped first when queue is full |

### 3.2 Canonical Event Schema (`ASTRAEvent`)

```python
@dataclass
class ASTRAEvent:
    event_type: AstraEventType | str
    source: str                         # e.g., "voice", "agent", "tool", "runtime"
    payload: dict[str, Any]             # Sanitized payload
    event_id: str                       # Unique UUID ("evt-...")
    timestamp: float                    # Epoch seconds
    request_id: Optional[str] = None    # Correlated user command ID
    correlation_id: Optional[str] = None
    priority: EventPriority = EventPriority.NORMAL
    metadata: dict[str, Any]
```

---

## 4. Standard Event Taxonomy (`AstraEventType`)

### Voice Subsystem
- `VOICE_SESSION_STARTED` / `VOICE_SESSION_ENDED`
- `VOICE_LISTENING_STARTED` / `VOICE_CAPTURING_STARTED`
- `VOICE_SPEECH_DETECTED` / `VOICE_SPEECH_ENDED`
- `VOICE_TRANSCRIBING` / `VOICE_TRANSCRIBED`
- `VOICE_SPEAKING_STARTED` / `VOICE_SPEAKING_STOPPED`
- `VOICE_INTERRUPTED` / `BARGE_IN_DETECTED`
- `WAKE_WORD_DETECTED`
- `VOICE_ERROR`

### Agent & Tool Subsystems
- `AGENT_STARTED`: Command ingestion with correlated `request_id`.
- `AGENT_THINKING`: Multi-step reasoning iteration.
- `AGENT_COMPLETED`: Successful response generation.
- `AGENT_FAILED`: Execution failure or timeout.
- `AGENT_CLARIFICATION_REQUESTED`: Assistant requests user clarification.
- `TOOL_STARTED`: Tool invocation before execution.
- `TOOL_COMPLETED`: Tool execution succeeded and verified.
- `TOOL_FAILED`: Tool execution failed or denied.

### Runtime, Task, Security & Health Subsystems
- `RUNTIME_STARTED` / `RUNTIME_READY` / `RUNTIME_STOPPING` / `RUNTIME_STOPPED` / `RUNTIME_ERROR`
- `TASK_CREATED` / `TASK_STARTED` / `TASK_COMPLETED` / `TASK_FAILED`
- `AUTOMATION_TRIGGERED` / `AUTOMATION_COMPLETED` / `AUTOMATION_FAILED`
- `PERMISSION_REQUESTED` / `CONFIRMATION_REQUESTED` / `ACTION_BLOCKED`
- `HEALTH_CHANGED`

---

## 5. Subsystem Adapters

### 5.1 `UIEventAdapter`
Bridges the internal `EventBus` to the React UI via `ConnectionManager` (WebSocket).
- Translates internal `ASTRAEvent` into the UI WebSocket envelope.
- Automatically handles thread boundaries (`asyncio.run_coroutine_threadsafe` when called from background threads).

### 5.2 `HealthAdapter`
Listens for failure events (`VOICE_ERROR`, `AGENT_FAILED`, `TOOL_FAILED`, `RUNTIME_ERROR`) and updates `HealthManager` subsystem statuses (`DEGRADED`, `UNHEALTHY`).

### 5.3 `LoggingAdapter`
Subscribes to all events (`*`) and produces structured, priority-aware logs with sanitized payload summaries.

---

## 6. Usage Examples

### Publishing an Event
```python
from src.core.events import ASTRAEvent, AstraEventType, EventPriority

# Asynchronous (queued, non-blocking)
event_bus.publish(
    ASTRAEvent(
        event_type=AstraEventType.TOOL_STARTED,
        source="tool",
        request_id="req-12345",
        payload={"tool": "open_application", "parameters": {"app_name": "notepad"}},
    )
)

# Synchronous (direct immediate dispatch, e.g. in tests)
event_bus.publish_sync(event)
```

### Subscribing to Events
```python
# Exact event type
event_bus.subscribe(AstraEventType.VOICE_INTERRUPTED, on_interrupt)

# Category wildcard
event_bus.subscribe("VOICE_*", on_voice_event)

# Global wildcard
event_bus.subscribe("*", on_any_event)
```
