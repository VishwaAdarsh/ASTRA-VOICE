# ASTRA V2 Capability Architecture & Registry Specification

## 1. Overview & Architectural Goals

The **Capability Architecture** in ASTRA V2 establishes a formal separation between **declared capabilities** (what ASTRA *can* do, under what policies, risks, and platforms) and **executable tools** (the concrete handlers that execute operations).

### Key Architectural Shifts:
1. **Capability vs. Tool Distinction**:
   - **Capability**: A platform-aware, policy-constrained, discoverable specification of functionality. It defines category, risk level, confirmation requirements, reversibility, input/output schemas, and state.
   - **Tool**: A concrete executable handler (e.g., Python class implementing `BaseTool` or async/sync callable) that performs the action when invoked.
2. **Deterministic Pre-Execution Validation**:
   - Every capability invocation must pass through input schema validation (`SchemaValidator`) *before* invoking handlers, preventing malformed LLM outputs from causing unexpected behavior or unhandled exceptions.
3. **5-Step Resolution Pipeline**:
   - Resolves capability IDs or legacy tool names through existence, platform compatibility, lifecycle state, dependency/health availability, and executable handler binding.
4. **Zero Silent Fallback**:
   - Missing dependencies or unconfigured providers fail deterministically with explicit typed errors (`CapabilityNotFoundError`, `CapabilityUnsupportedPlatformError`, `CapabilityDisabledError`, `CapabilityUnavailableError`), never silently degrading to fake or mock data in production.

---

## 2. Core Capability Models (`src/core/capabilities/models.py`)

### 2.1 Enums

#### `CapabilityCategory`
- `CONVERSATION`: Direct conversational or dialog responses.
- `SYSTEM`: OS-level utilities (volume, system info, resource monitor).
- `DESKTOP`: Window management, active application control, desktop navigation.
- `FILESYSTEM`: File and folder operations (create, read, copy, move, delete).
- `WEB`: Browser automation, web search, webpage fetching.
- `MEMORY`: Long-term and short-term memory storage and retrieval.
- `VISION`: Screen capture, OCR, visual layout analysis.
- `TASKS`: Task tracking, task scheduling, checklist management.
- `AUTOMATION`: Background workflows, triggers, notification management.
- `COMMUNICATION`: Email, messaging, notifications.
- `SECURITY`: Security audits, permission checks, injection defense.
- `OTHER`: Miscellaneous extensions.

#### `RiskLevel`
- `RISK_0` (None): Read-only operations with no privacy or system impact (e.g., system time).
- `RISK_1` (Low): Read-only operations accessing local public metadata (e.g., file metadata, list memories).
- `RISK_2` (Medium): Safe operations modifying non-critical state (e.g., volume control, remember note).
- `RISK_3` (High): Operations altering system or application state (e.g., launch app, move file, close app).
- `RISK_4` (Critical): Destructive or privacy-sensitive operations (e.g., delete file, clear memories).
- `RISK_5` (Restricted): Administrative or security-sensitive actions requiring explicit operator elevation and confirmation.

#### `CapabilityState`
- `REGISTERED`: Capability is registered but not yet initialized or activated.
- `ENABLED`: Fully operational and available for execution and LLM tool calling.
- `DISABLED`: Temporarily disabled by policy or user setting; rejected if invoked.
- `UNAVAILABLE`: Dependencies or hardware unavailable (e.g., missing API key, missing device).
- `DEGRADED`: Partially available with reduced functionality.

### 2.2 `CapabilityDefinition` Dataclass

```python
@dataclass
class CapabilityDefinition:
    capability_id: str                      # Format: "<category>.<action>" (e.g., "filesystem.create_file")
    name: str                              # Human-readable name
    description: str                       # Detailed description for LLM prompts & UI
    category: CapabilityCategory           # Functional domain
    risk_level: RiskLevel = RiskLevel.RISK_1
    input_schema: dict[str, Any] = ...     # JSON Schema for parameters
    output_schema: dict[str, Any] = ...    # JSON Schema for return values
    requires_confirmation: bool = False     # Explicit user confirmation prompt
    read_only: bool = False                # Does not mutate state
    reversible: bool = False               # Supports rollback/undo
    platforms: list[str] = ["windows"]     # Supported operating systems
    dependencies: list[str] = []           # Required services or system packages
    state: CapabilityState = REGISTERED    # Lifecycle state
    handler: Optional[Callable] = None     # Callable or BaseTool instance
```

---

## 3. Capability Registry (`src/core/capabilities/registry.py`)

The `CapabilityRegistry` provides a thread-safe, canonical repository for all capabilities.

### Key Capabilities:
- **Registration**: Enforces valid ID formatting (`<category>.<action>`) and prevents accidental duplicate registrations unless explicitly overwriting.
- **Queries & Filtering**: Filter by `category`, `state`, `risk_level`, or `platform`.
- **State Management**: Modify state (`enable()`, `disable()`, `set_state()`) dynamically.
- **Health Synchronization**: Synchronizes capability states with `HealthManager` based on component degradation or dependency failures.
- **Legacy Tool Mapping**: `ToolRegistry` embeds `CapabilityRegistry`, automatically translating legacy `BaseTool` registrations into standard `CapabilityDefinition` records with backward-compatible name alias lookups.

---

## 4. Capability Resolver (`src/core/capabilities/resolver.py`)

The `CapabilityResolver` verifies whether a requested capability can safely execute.

### Resolution Steps:
1. **Existence Check**: Look up the capability by ID or alias. Raises `CapabilityNotFoundError` if absent.
2. **Platform Support**: Verifies the host OS (`windows`, `linux`, `darwin`) against `supported_platforms`. Raises `CapabilityUnsupportedPlatformError` if incompatible.
3. **State Verification**: Ensures capability is `ENABLED` or `REGISTERED`. Raises `CapabilityDisabledError` if `DISABLED`.
4. **Availability Verification**: Verifies capability is not `UNAVAILABLE`. Raises `CapabilityUnavailableError` if dependencies or required components are missing.
5. **Handler Binding**: Ensures an executable handler (`BaseTool` or callable) is bound. Raises `CapabilityResolutionError` if missing.

---

## 5. Parameter Validation (`src/core/capabilities/validation.py`)

The `SchemaValidator` provides lightweight, deterministic JSON schema validation for capability arguments:
- **Type Checking**: Validates `string`, `integer`, `number`, `boolean`, `array`, and `object`.
- **Required Fields**: Ensures all mandatory properties declared in `required` are present.
- **Enum Validation**: Verifies argument values against allowed enum sets.
- **Error Reporting**: Raises `CapabilityValidationError` with clear, actionable error messages before execution begins.

---

## 6. Execution Pipeline Integration (`src/execution/executor.py`)

The `ToolExecutor` coordinates execution across the capability lifecycle:

```
LLM / Request
     │
     ▼
ToolExecutor.execute(tool_name, params)
     │
     ├─► 1. Resolve via CapabilityResolver
     │        (existence, platform, state, availability, handler)
     │
     ├─► 2. Validate input parameters via SchemaValidator
     │
     ├─► 3. Enforce Permissions (PermissionManager)
     │        (maps RiskLevel.RISK_5 -> RESTRICTED)
     │
     ├─► 4. Enforce Confirmation (ConfirmationHandler)
     │        (if requires_confirmation or elevated risk)
     │
     ├─► 5. Emit Event: CAPABILITY_EXECUTION_STARTED
     │
     ├─► 6. Execute Handler (tool.run or async callable)
     │
     ├─► 7. Emit Event: CAPABILITY_EXECUTION_COMPLETED / FAILED
     │
     └─► 8. Return ToolResult
```

---

## 7. Event Bus Integration (`src/core/events/models.py`)

The following events are emitted to the central `EventBus`:
- `capability_registered`: Emitted when a new capability is registered.
- `capability_state_changed`: Emitted when a capability transitions between states (`ENABLED`, `DISABLED`, etc.).
- `capability_execution_started`: Emitted before handler execution begins.
- `capability_execution_completed`: Emitted upon successful execution.
- `capability_execution_failed`: Emitted upon execution error or validation failure.

---

## 8. LLM Schema Adapter (`src/core/capabilities/schemas.py`)

`LLMToolSchemaAdapter` dynamically produces provider-ready function-calling schemas (OpenAI / Gemini / Claude compatible) directly from active capabilities:
- Automatically filters out capabilities that are not executable on the host platform.
- Excludes capabilities marked internal or with `expose_to_llm = False`.
- Converts schemas to OpenAI function calling specifications with parameters and types.
- Supports short tool names (e.g., `open_application`) for backward compatibility with model weights and prompt templates.
