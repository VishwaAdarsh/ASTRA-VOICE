# ASTRA Desktop Control & Automation — Repository Audit

## 1. Executive Summary

This audit evaluates the ASTRA repository's architecture, security boundaries, and execution pipeline to safely implement Windows desktop control capabilities. The audit focuses on:
- **Application Launching**: Safe, allowlisted desktop application launching without shell interpolation.
- **File and Folder Search**: Constrained, depth-bounded, time-bounded searches in approved roots (Downloads, Documents, Desktop) without path traversal or destructive operations.
- **Clipboard Operations**: Explicit, user-requested read and write operations with strict privacy safeguards.
- **Orchestration Integrity**: Integration with the existing `AstraAgent`, `CapabilityRegistry`, `ToolExecutor`, `EventBus`, Ollama Cloud LLM provider, and ElevenLabs natural voice pipeline.

---

## 2. Component Discovery & Entry Points

### 2.1 Primary Application Entry Point
- **File**: [`main.py`](file:///c:/Users/Pradeep/Documents/GitHub/ASTRA-VOICE/main.py)
- **Lifecycle**:
  1. Parses CLI flags (`--cli`, `--backend`, `--port`, `--debug`).
  2. Resolves free port dynamically (8000–8020) via `find_available_port()`.
  3. Writes runtime config (`astra_runtime_config.json`) for frontend discovery.
  4. Calls `SystemLifecycle.startup()` which initializes the SQLite database (`data/astra_memory.db`), crash recovery audit, and creates `AstraAgent`.
  5. Initializes `VoiceManager` (sounddevice mic, VAD, STT, ElevenLabs TTS, wake-word listener).
  6. Starts background FastAPI/WebSocket server thread (`uvicorn.Server`).
  7. Launches desktop shell: `AstraWebWindow` (`src/ui/web_shell.py`, PySide6 QtWebEngine shell loading the React Vite frontend at `http://127.0.0.1:{bound_port}`). Falls back to `InteractiveCLI` if PySide6 fails.

### 2.2 Cognitive Agent & LLM Architecture
- **Files**:
  - [`src/brain/agent.py`](file:///c:/Users/Pradeep/Documents/GitHub/ASTRA-VOICE/src/brain/agent.py): Central cognitive orchestrator running a controlled multi-step loop (up to 5 iterations).
  - [`src/brain/llm/client.py`](file:///c:/Users/Pradeep/Documents/GitHub/ASTRA-VOICE/src/brain/llm/client.py): LLM client with retry, backoff, and health monitoring.
  - [`src/brain/llm/factory.py`](file:///c:/Users/Pradeep/Documents/GitHub/ASTRA-VOICE/src/brain/llm/factory.py): Provider factory instantiating `OllamaProvider`, `GeminiProvider`, or `MockLLMProvider`.
  - [`src/brain/llm/ollama_provider.py`](file:///c:/Users/Pradeep/Documents/GitHub/ASTRA-VOICE/src/brain/llm/ollama_provider.py): Connects to `https://ollama.com/api/chat` (e.g. `gemma4:31b`) using `Bearer $OLLAMA_API_KEY`, supporting structured function/tool schemas and native tool calling without leaking credentials.

### 2.3 Voice Subsystem (STT, TTS, Barge-in)
- **Files**:
  - [`src/voice/manager.py`](file:///c:/Users/Pradeep/Documents/GitHub/ASTRA-VOICE/src/voice/manager.py): High-level voice facade.
  - [`src/voice/session.py`](file:///c:/Users/Pradeep/Documents/GitHub/ASTRA-VOICE/src/voice/session.py): Finite state machine (`IDLE` $\rightarrow$ `LISTENING` $\rightarrow$ `CAPTURING` $\rightarrow$ `PROCESSING` $\rightarrow$ `SPEAKING` $\rightarrow$ `IDLE`).
  - [`src/voice/elevenlabs_provider.py`](file:///c:/Users/Pradeep/Documents/GitHub/ASTRA-VOICE/src/voice/elevenlabs_provider.py): Streams 16kHz linear PCM audio directly to `sounddevice`. Features instant interruption via `stop()` and secret scrubbing via `sanitize_text_for_speech()`.
  - [`src/voice/barge_in.py`](file:///c:/Users/Pradeep/Documents/GitHub/ASTRA-VOICE/src/voice/barge_in.py): Monitors microphone during TTS output; halts playback immediately if user interrupts.

### 2.4 Capability Registry, Tool Execution & Verification
- **Files**:
  - [`src/core/capabilities/registry.py`](file:///c:/Users/Pradeep/Documents/GitHub/ASTRA-VOICE/src/core/capabilities/registry.py): Central capability registry enforcing risk tiers (`RISK_1` to `RISK_4`), read-only flags, and platform compatibility.
  - [`src/tools/registry.py`](file:///c:/Users/Pradeep/Documents/GitHub/ASTRA-VOICE/src/tools/registry.py): Bridges tool implementations (`BaseTool`) into `CapabilityRegistry`.
  - [`src/execution/executor.py`](file:///c:/Users/Pradeep/Documents/GitHub/ASTRA-VOICE/src/execution/executor.py): Orchestrates capability resolution, OpenAPI schema validation, pre-execution verification, permission gating, tool invocation, and post-execution verification.
  - [`src/execution/verifier.py`](file:///c:/Users/Pradeep/Documents/GitHub/ASTRA-VOICE/src/execution/verifier.py): Validates pre-conditions and post-conditions for actions.

---

## 3. Current Implementation Status of Desktop Capabilities

| Capability | Current State | Evidence / Location | Gaps & Issues |
|---|---|---|---|
| **Application Launching** | **Partially Implemented** | `src/tools/applications/launcher.py`, `aliases.py` | 1. **No Evidence Verification**: Claims `{app} opened.` without checking if process spawned.<br>2. **Already-Running Not Handled**: Launches duplicate instance or reports success even if already running.<br>3. **Missing Windows Settings**: "settings" / "windows settings" is unmapped.<br>4. **Browser Fragility**: `"browser"` alias hardcoded to `"chrome.exe"`; fails if Chrome is absent even though Edge is pre-installed. |
| **Application Status** | **Partially Implemented / Unsafe** | `src/tools/applications/status.py` | Uses `subprocess.check_output(f'tasklist ... {exe_name}', shell=True)`. Formatted string with `shell=True` is an architectural and security defect. Must use safe argument array or `psutil`. |
| **File / Folder Search** | **Partially Implemented** | `src/tools/filesystem/search.py`, `paths.py` | 1. **Unbounded Recursion**: `target_folder.rglob("*")` has no maximum depth limit.<br>2. **No Execution Timeout**: Large directory trees can hang the execution thread.<br>3. **Crashes on Permission Denied**: Unhandled `PermissionError` on system/protected subdirectories.<br>4. **Loose Root Policy**: Allows arbitrary subfolders under `USERPROFILE` outside approved roots (`Downloads`, `Documents`, `Desktop`). |
| **Clipboard Operations** | **Missing** | `src/brain/context/collectors.py` (read-only context inspect only) | No `read_clipboard` or `write_clipboard` tool registered in `ToolRegistry`. Need safe, privacy-preserving tools with explicit user intent and secret sanitization. |
| **Voice TTS Output** | **Implemented & Verified** | `src/voice/elevenlabs_provider.py` | Operational. After tool execution, agent formats response, sanitizes secrets, and speaks via ElevenLabs. |

---

## 4. Security Risks & Vulnerability Analysis

1. **Shell Interpolation in Status Tool**:
   `status.py` line 42 calls `subprocess.check_output(f'tasklist /FI "IMAGENAME eq {exe_name}"', shell=True)`.
   *Remediation*: Replace with `psutil` process iteration or `subprocess.check_output(["tasklist", "/FI", ...], shell=False)`.
2. **Unbounded Filesystem Traversal**:
   `search.py` performs unconstrained `rglob("*")`.
   *Remediation*: Restrict searches to explicitly allowlisted root folders (`Downloads`, `Documents`, `Desktop`, or specific user-configured project roots). Enforce maximum traversal depth (default 3 levels), result limits (max 20), and timeout enforcement (default 5.0 seconds). Handle `PermissionError` and `OSError` cleanly.
3. **Premature / Fake Success Messaging**:
   `launcher.py` assumes `Popen` succeeded without checking exit codes or verifying whether the process spawned.
   *Remediation*: Check process existence via `psutil` or active process handle before reporting success. If the app was already running, inform the user honestly (`"Calculator is already open."`). If the executable failed to launch, return `ExecutionStatus.FAILED`.
4. **Clipboard Content Privacy**:
   Clipboard reading must only occur when explicitly instructed by the user. Clipboard content must never be logged to disk or console. All text retrieved must pass through `SecretRedactionFilter` to prevent accidental credential ingestion.

---

## 5. Minimal Implementation Plan

### Step 1: Safe Process Inspection Utility
- Implement a helper using `psutil` to safely check if an executable/application is already running without shell commands.

### Step 2: Upgrade Application Launcher (`OpenApplicationTool`)
- Expand `ApplicationRegistry` in `src/tools/applications/aliases.py`:
  - Add `"settings"` / `"windows settings"` (`"ms-settings:"`).
  - Add smart browser detection (checks Chrome, Edge, Brave, Firefox, or default system browser).
- Upgrade `OpenApplicationTool.execute()`:
  - Check if application is already running. If so, report truthful status and evidence without duplicate spawn.
  - Launch with `subprocess.Popen([executable], shell=False)` or safe Windows shell URI handler for `ms-settings:`.
  - Verify launch evidence via brief process table check before returning `ExecutionStatus.SUCCESS`.

### Step 3: Harden File Search (`SearchFilesTool`)
- Upgrade `SearchFilesTool.execute()`:
  - Restrict base directory strictly to approved roots: `Downloads`, `Documents`, `Desktop`, or safe project directories.
  - Implement bounded iterative directory walk (`os.scandir` or `Path.iterdir`) with `max_depth=3`.
  - Implement execution timeout (5.0s) and maximum result count (max 20).
  - Handle `PermissionError` and inaccessible files gracefully without terminating the search.
  - Return clean file metadata (name, path, size, modified timestamp) without reading file contents.

### Step 4: Implement Safe Clipboard Capabilities
- Create `src/tools/system/clipboard.py` with:
  - `ReadClipboardTool` (`read_clipboard`): Reads text from the Windows clipboard via Windows API (`win32clipboard` or `ctypes user32`), scrubs secrets via `SecretRedactionFilter`, and returns text preview. Rejects binary/image content safely.
  - `WriteClipboardTool` (`write_clipboard`): Writes user-supplied text to the Windows clipboard safely.
- Register tools in `ToolRegistry` and `CapabilityRegistry` under `CapabilityCategory.SYSTEM` (`RISK_1` for read, `RISK_2` for write).

### Step 5: Verify End-to-End Voice & LLM Integration
- Verify that `AstraAgent` interprets spoken/typed commands, invokes the capability, formats a concise summary, and ElevenLabs speaks the result naturally.
- Run comprehensive tests in `tests/test_desktop_control.py` covering application launching, rejection of unallowed apps, file search within bounds, path traversal rejection, clipboard read/write, and secret protection.
