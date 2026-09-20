# ASTRA V2 — Phase 10: Capability Registry & Tool Architecture Audit

**Date:** 2026-09-20  
**Status:** Audit Complete  

---

## 1. Executive Summary

This audit assesses the current tool and execution architecture of ASTRA Voice Assistant across all implemented phases (V2-01 through V2-09). 

Currently, ASTRA defines 31 executable tools as subclasses of `BaseTool`, registered into an in-memory `ToolRegistry`. While this model provides basic registration and execution, it lacks a formal distinction between **declared capabilities** (what the system can do, its risk, policies, platform constraints, schemas, and dependencies) and **tools** (the concrete execution handlers). 

Phase V2-10 establishes a canonical **Capability Registry** that evolves the existing `ToolRegistry` rather than creating a competing parallel registry, ensuring backward compatibility while empowering `AstraAgent`, `ToolExecutor`, `PermissionManager`, `HealthManager`, and the V2-09 `EventBus`.

---

## 2. Current Tool Architecture

### 2.1 Tool Definition (`src/tools/base.py`)
- All tools inherit from `BaseTool`.
- Defines attributes:
  - `name: str`: Tool identifier (e.g., `"open_application"`, `"search_files"`).
  - `description: str`: Natural language summary for the LLM.
  - `permission_level: PermissionLevel`: Enum (`SAFE`, `CONFIRM`, `RESTRICTED`).
  - `expose_to_llm: bool`: Toggle for LLM schema inclusion.
  - `parameters_schema: dict[str, Any]`: JSON Schema describing arguments.
- Abstract methods:
  - `validate(parameters: dict[str, Any]) -> bool`: Manual, per-tool validation.
  - `execute(parameters: dict[str, Any]) -> ToolResult`: Concrete handler execution.
  - `get_schema() -> dict[str, Any]`: Formats OpenAPI/JSON tool schema.

### 2.2 Tool Registration (`src/tools/registry.py`)
- `ToolRegistry` holds `self._tools: dict[str, BaseTool]` keyed by lowercased tool names.
- Methods: `register(tool)`, `get(name)`, `contains(name)`, `has_tool(name)`, `list_tools()`.
- Registration is performed during `AstraAgent.__init__` in `_register_default_tools()`.

### 2.3 Tool Discovery & LLM Schema Generation (`src/brain/prompts/tool_selection.py`)
- `generate_tool_schemas(registry)` iterates `registry.list_tools()`.
- Checks `expose_to_llm`, deduplicates names, and returns a list of dictionaries: `[{"name": ..., "description": ..., "parameters": ...}]`.
- In `AstraAgent.process_command`, this list is passed to `llm_client.generate_decision(tool_schemas=tool_schemas)`.

### 2.4 Tool Execution Pipeline (`src/execution/executor.py`)
```
ToolRequest (tool_name, parameters)
  ↓
1. Registry Lookup: registry.get(tool_name)
  ↓
2. Pre-execution Verification: verifier.verify_pre_execution(tool.name, params)
  ↓
3. Permission Check: permission_manager.is_permitted(request, tool.permission_level)
  ↓
4. User Confirmation Check: confirmation_handler.confirm(...) if CONFIRM
  ↓
5. Tool Validation: tool.validate(request.parameters)
  ↓
6. Tool Execution: tool.execute(request.parameters)
  ↓
7. Post-execution Verification: verifier.verify_post_execution(result, ...)
  ↓
ToolResult
```

### 2.5 Security, Permissions & Confirmation
- `PermissionManager` (`src/security/permissions.py`):
  - Checks `request.tool_name` against `PermissionLevel` (`SAFE` → True, `CONFIRM` → True with handler, `RESTRICTED` → False).
- `ConfirmationHandler` (`src/security/confirmation.py`):
  - `ConsoleConfirmationHandler` prompts CLI user; `AutoApproveConfirmationHandler` for tests.
- `SecurityAuditor` (`src/security/auditor.py`):
  - Records execution events, applies secret redaction (`SecretRedactionFilter`).

### 2.6 Health & Availability (`src/core/health.py`)
- `HealthManager` monitors 9 subsystems: `STT`, `TTS`, `LLM`, `Vision`, `OCR`, `Web`, `Database`, `Scheduler`, `TaskEngine`.
- Statuses: `HEALTHY`, `READY`, `DEGRADED`, `UNAVAILABLE`, `DISABLED`, `UNKNOWN`.
- *Gap*: Tool availability is not dynamically connected to subsystem health; if Web provider is down, `search_web` still advertises itself to the LLM and fails during execution.

### 2.7 Event Bus Integration (`src/core/events/`)
- Delivered in Phase V2-09:
  - `EventBus` with priority queue (`CRITICAL`, `HIGH`, `NORMAL`, `LOW`), worker thread, subscriber error isolation, backpressure handling, and `sync_mode`.
  - Adapters: `UIEventAdapter`, `HealthAdapter`, `LoggingAdapter`.
  - Emits `TOOL_STARTED`, `TOOL_COMPLETED`, `TOOL_FAILED` in `AstraAgent`.

---

## 3. Existing Tools & Capability Migration Table

The repository currently registers exactly 31 tools. Below is the canonical capability mapping:

| # | Current Tool Name | Canonical Capability ID | Category | Risk Level | Read Only | Reversible | Requires Confirmation | Dependencies | Supported Platforms | Existing Status |
|---|-------------------|-------------------------|----------|------------|-----------|------------|-----------------------|--------------|---------------------|-----------------|
| 1 | `open_application` | `system.open_application` | `system` | `RISK_2` | False | True | False | Windows OS | `["windows"]` | Production |
| 2 | `close_application` | `system.close_application` | `system` | `RISK_2` | False | True | False | Windows OS | `["windows"]` | Production |
| 3 | `open_project` | `system.open_project` | `system` | `RISK_2` | False | True | False | Windows OS | `["windows"]` | Production |
| 4 | `application_status` | `system.application_status` | `system` | `RISK_1` | True | True | False | Windows OS | `["windows"]` | Production |
| 5 | `open_website` | `web.open_website` | `web` | `RISK_2` | False | True | False | Browser / Network | `["windows", "linux", "darwin"]` | Production |
| 6 | `search_web` | `web.search` | `web` | `RISK_1` | True | True | False | Web Search Provider | `["windows", "linux", "darwin"]` | Production |
| 7 | `fetch_webpage` | `web.fetch_webpage` | `web` | `RISK_1` | True | True | False | Network | `["windows", "linux", "darwin"]` | Production |
| 8 | `research_topic` | `web.research_topic` | `web` | `RISK_1` | True | True | False | Web Search Provider | `["windows", "linux", "darwin"]` | Production |
| 9 | `system_information` | `system.system_information` | `system` | `RISK_1` | True | True | False | Windows OS | `["windows"]` | Production |
| 10 | `resource_information` | `system.resource_information` | `system` | `RISK_1` | True | True | False | Windows OS | `["windows"]` | Production |
| 11 | `screenshot` | `system.screenshot` | `system` | `RISK_1` | True | True | False | Display / GDI | `["windows"]` | Production |
| 12 | `volume_control` | `system.volume_control` | `system` | `RISK_2` | False | True | False | Windows Audio Endpoint | `["windows"]` | Production |
| 13 | `open_folder` | `filesystem.open_folder` | `filesystem` | `RISK_2` | False | True | False | Windows Explorer | `["windows"]` | Production |
| 14 | `search_files` | `filesystem.search_files` | `filesystem` | `RISK_1` | True | True | False | Local Filesystem | `["windows", "linux", "darwin"]` | Production |
| 15 | `file_metadata` | `filesystem.file_metadata` | `filesystem` | `RISK_1` | True | True | False | Local Filesystem | `["windows", "linux", "darwin"]` | Production |
| 16 | `open_file` | `filesystem.open_file` | `filesystem` | `RISK_2` | False | True | False | Windows OS | `["windows"]` | Production |
| 17 | `create_folder` | `filesystem.create_folder` | `filesystem` | `RISK_2` | False | True | False | Local Filesystem | `["windows", "linux", "darwin"]` | Production |
| 18 | `create_text_file` | `filesystem.create_text_file` | `filesystem` | `RISK_2` | False | True | False | Local Filesystem | `["windows", "linux", "darwin"]` | Production |
| 19 | `rename_file` | `filesystem.rename_file` | `filesystem` | `RISK_3` | False | True | False | Local Filesystem | `["windows", "linux", "darwin"]` | Production |
| 20 | `move_file` | `filesystem.move_file` | `filesystem` | `RISK_3` | False | True | False | Local Filesystem | `["windows", "linux", "darwin"]` | Production |
| 21 | `copy_file` | `filesystem.copy_file` | `filesystem` | `RISK_2` | False | True | False | Local Filesystem | `["windows", "linux", "darwin"]` | Production |
| 22 | `delete_file` | `filesystem.delete_file` | `filesystem` | `RISK_4` | False | False | True | Local Filesystem | `["windows", "linux", "darwin"]` | Production |
| 23 | `organize_folder` | `filesystem.organize_folder` | `filesystem` | `RISK_3` | False | True | True | Local Filesystem | `["windows", "linux", "darwin"]` | Production |
| 24 | `remember` | `memory.remember` | `memory` | `RISK_2` | False | True | False | SQLite Database | `["windows", "linux", "darwin"]` | Production |
| 25 | `retrieve_memory` | `memory.retrieve` | `memory` | `RISK_1` | True | True | False | SQLite Database | `["windows", "linux", "darwin"]` | Production |
| 26 | `forget_memory` | `memory.forget` | `memory` | `RISK_3` | False | False | True | SQLite Database | `["windows", "linux", "darwin"]` | Production |
| 27 | `list_memories` | `memory.list` | `memory` | `RISK_1` | True | True | False | SQLite Database | `["windows", "linux", "darwin"]` | Production |
| 28 | `analyze_screen` | `vision.analyze_screen` | `vision` | `RISK_1` | True | True | False | Screen Capture / Vision Provider | `["windows"]` | Production |
| 29 | `analyze_active_window` | `vision.analyze_active_window` | `vision` | `RISK_1` | True | True | False | Active Window / Vision Provider | `["windows"]` | Production |
| 30 | `analyze_image` | `vision.analyze_image` | `vision` | `RISK_1` | True | True | False | Vision Provider | `["windows", "linux", "darwin"]` | Production |
| 31 | `read_screen_text` | `vision.read_screen_text` | `vision` | `RISK_1` | True | True | False | OCR Provider | `["windows"]` | Production |

---

## 4. Architectural Gaps & Problems Identified

1. **No Capability vs. Tool Separation**: The LLM is given direct names of Python tool classes. The Agent cannot reason about capabilities independently of tool implementations.
2. **Missing Risk & Reversibility Metadata**: Only 3 permission levels (`SAFE`, `CONFIRM`, `RESTRICTED`) exist. No distinction between read-only actions, reversible actions, and irreversible/destructive actions (`delete_file`, `forget_memory`).
3. **Missing Platform Awareness**: Windows-only tools (`screenshot`, `volume_control`, `open_application`) don't declare platform constraints; they fail deep in Windows API calls if invoked elsewhere.
4. **Static Tool Exposure**: All 31 tools are dumped into the LLM prompt on every single turn, bloating token usage and creating distraction for simple queries.
5. **Disconnected Health System**: If a subsystem (e.g. `Vision` or `Web`) is degraded or unavailable in `HealthManager`, its tools remain advertised and fail at execution time.
6. **Unchecked Schema Validation**: `BaseTool.validate(parameters)` is ad-hoc Python code per tool, with no centralized JSON schema validation before passing arguments to the tool.

---

## 5. Migration Plan for Phase V2-10

1. **Create Canonical Capability Models (`src/core/capabilities/models.py`)**:
   - `CapabilityId`: Stable namespace pattern (`category.action`).
   - `CapabilityCategory`: `conversation`, `system`, `desktop`, `filesystem`, `web`, `memory`, `vision`, `tasks`, `automation`, `communication`, `security`, `other`.
   - `RiskLevel`: `RISK_0` through `RISK_5`.
   - `CapabilityState`: `REGISTERED`, `ENABLED`, `DISABLED`, `UNAVAILABLE`, `DEGRADED`.
   - `CapabilityDefinition`: Full metadata container (input schema, platform, dependencies, risk, confirmation, read-only, reversible, supports-undo).

2. **Create Capability Registry & Resolver (`src/core/capabilities/registry.py`, `resolver.py`)**:
   - Thread-safe registry with deterministic duplicate rejection.
   - Capability resolver that validates existence, platform compatibility, and availability before returning an approved handler.
   - Evolve `ToolRegistry` to delegate to/wrap `CapabilityRegistry` so existing code continues working.

3. **Input Schema Validation & LLM Adapter (`src/core/capabilities/schemas.py`, `validation.py`)**:
   - Centralized JSON schema argument validation before execution.
   - `LLMToolSchemaAdapter` converting capabilities into LLM-consumable tool definitions.

4. **Integration with Agent, Executor, Security, Health, and Event Bus**:
   - `AstraAgent`: Discovers capabilities via `CapabilityRegistry`.
   - `ToolExecutor`: Resolves requested action via `CapabilityResolver`, runs input validation, evaluates risk/confirmation, executes handler, emits Event Bus events.
   - `HealthManager`: Dynamically syncs subsystem health with capability availability.
   - `EventBus`: Publishes `CAPABILITY_*` lifecycle and execution events.

---

## 6. Files Changed in Phase V2-10

### New Files:
- `docs/ASTRA_V2_CAPABILITY_AUDIT.md` (this audit document)
- `docs/ASTRA_V2_CAPABILITY_ARCHITECTURE.md` (architectural reference)
- `src/core/capabilities/__init__.py`
- `src/core/capabilities/models.py`
- `src/core/capabilities/errors.py`
- `src/core/capabilities/registry.py`
- `src/core/capabilities/resolver.py`
- `src/core/capabilities/schemas.py`
- `src/core/capabilities/validation.py`
- `tests/test_capabilities.py`

### Modified Files:
- `src/tools/registry.py` (evolved to bridge with `CapabilityRegistry`)
- `src/execution/executor.py` (resolves via `CapabilityResolver`, performs schema validation and risk evaluation)
- `src/brain/agent.py` (uses `CapabilityRegistry` and `LLMToolSchemaAdapter`)
- `src/core/events/models.py` (adds `CAPABILITY_*` event types)
