# ASTRA — Windows Desktop Control & Automation Architecture

This document describes the design, implementation, and security guarantees of the ASTRA Desktop Control & Automation subsystem.

---

## 1. Subsystem Architecture Overview

ASTRA Desktop Control extends the assistant with safe, deterministic Windows automation capabilities while preserving the centralized capability, permission, verification, and LLM orchestration architecture.

```
                           +----------------------+
                           |   User Voice/Text    |
                           +----------+-----------+
                                      |
                                      v
                           +----------------------+
                           |      ASTRA Agent     |
                           +----------+-----------+
                                      |
                      +---------------+---------------+
                      |                               |
                      v                               v
             +------------------+           +-------------------+
             | Capability Engine|           |  Tool Executor    |
             |  & Tool Registry |           |  & Verifier       |
             +--------+---------+           +---------+---------+
                      |                               |
      +---------------+---------------+---------------+
      |                               |               |
      v                               v               v
+-----------------------+ +--------------------+ +-------------------+
|  Application Launcher | | File & Folder Search| | Clipboard Control |
|  - Allowlist registry | | - Approved roots   | | - ctypes API      |
|  - psutil inspection  | | - Depth <= 3       | | - Secret scrub    |
|  - Safe arguments     | | - Timeout <= 5s    | | - No disk logging |
|  - Launch evidence    | | - Caps <= 20       | | - Zero shell      |
+-----------------------+ +--------------------+ +-------------------+
      |                               |               |
      +---------------+---------------+---------------+
                      |
                      v
             +------------------+
             | Speech Sanitizer |
             +--------+---------+
                      |
                      v
             +------------------+
             | ElevenLabs / TTS |
             +------------------+
```

---

## 2. Capabilities Implemented

### A. Application Launcher (`open_application`, `application_status`)

1. **Strict Allowlist Registry**:
   - Approved applications: `notepad`, `calculator`, `settings` (`ms-settings:`), `browser`, `edge`, `chrome`, `brave`, `firefox`, `vscode` (`code`), `paint` (`mspaint`), `explorer`, `terminal` (`cmd`, `wt`).
   - Unapproved executables (e.g. `powershell.exe`, `regedit.exe`, arbitrary scripts) are rejected before execution with `ExecutionStatus.INVALID_REQUEST`.
2. **Safe Executable & Alias Resolution**:
   - Standard Windows install paths (`Program Files`, `Program Files (x86)`, `LocalAppData`).
   - Dynamic browser fallback (evaluates Chrome $\rightarrow$ Edge $\rightarrow$ Brave $\rightarrow$ Firefox).
   - Windows Settings protocol URI (`ms-settings:`) launched safely via native `os.startfile`.
3. **Safe Process Spawning**:
   - Strictly `shell=False`. Arguments are passed as validated argument lists to `subprocess.Popen`.
   - Creation flag `DETACHED_PROCESS` decouples process lifecycles from backend shutdowns without console window flashing.
4. **Already-Running Process Detection**:
   - Powered by `psutil.process_iter(['pid', 'name'])` with non-shell `tasklist` fallback.
   - Detects Windows 10/11 process name mappings (e.g., `calc.exe` $\leftrightarrow$ `CalculatorApp.exe`).
   - If `check_already_running=True` is provided, reports truthful status (`"{App} is already running."`) without duplicate process spawning.
5. **Launch Evidence Verification**:
   - Verifies process handle immediately following `Popen`.
   - Detects instant exit codes (`proc.poll() != 0`) and verifies PID assignment.
   - Returns honest `ExecutionStatus.NOT_FOUND` if executable is missing from disk and PATH.

### B. File & Folder Search (`search_files`)

1. **Approved Content Roots**:
   - Enforces user content boundaries: `Downloads`, `Documents`, `Desktop`, `Pictures`, `Videos`, `Music`, and configured project directories (`Documents/GitHub`, `Projects`).
   - Test sandbox environments are strictly bounded to the isolated sandbox root.
   - Explicitly rejects path traversal (`..`), system directories (`C:\Windows`, `C:\Program Files`, `C:\System32`), and unauthorized drives.
2. **Bounded Traversal**:
   - **Depth Bounded**: Traversal depth strictly bounded to $\le 3$ directory levels (`max_depth <= 3`).
   - **Time Bounded**: Execution timeout capped at 5.0 seconds (`timeout_sec <= 5.0s`).
   - **Result Capped**: Maximum returned results capped at 20 (`limit <= 20`).
   - Ignores heavy developer directories (`node_modules`, `.git`, `__pycache__`, `$recycle.bin`, `appdata`) for responsive performance.
3. **Permission Error Tolerance**:
   - Gracefully catches `PermissionError` and `OSError` per directory and file; never crashes on protected junctions or locked files.
4. **Metadata-Only Results**:
   - Returns only safe file metadata: `name`, `path`, `parent`, `extension`, `size`, `modified`.
   - Never inspects, extracts, or exposes file contents during search.
5. **Natural Voice Summaries**:
   - Formulates concise, conversational voice messages:
     - *"Found 3 files matching 'invoice' in Documents."*
     - *"No files matching 'taxes' were found in Downloads."*

### C. Clipboard Operations (`read_clipboard`, `write_clipboard`)

1. **Native 64-bit Windows ctypes Integration**:
   - Direct integration with Win32 APIs (`user32` and `kernel32`) with explicit 64-bit pointer and handle prototypes (`HWND`, `HANDLE`, `HGLOBAL`, `c_size_t`, `c_void_p`).
   - Zero external third-party dependencies (`pyperclip` not required).
   - In-memory fallback buffer ensures cross-platform and headless CI test compatibility.
2. **Strict Secret Scrubbing**:
   - All text retrieved from the clipboard passes through `SecretRedactionFilter.redact()`.
   - Automatically sanitizes API keys (`sk_...`, `ak_...`), bearer tokens, passwords, and private tokens into `[REDACTED]`.
3. **Zero Persistence Guarantee**:
   - Raw clipboard contents are **never** logged to log files, console, database, or disk.
   - Audit logs capture only character counts and redaction flags.
4. **Graceful Status Handling**:
   - Empty clipboard or non-text clipboard data reports clean, non-erroneous voice status:
     - *"Clipboard is empty or contains non-text data."*
     - *"Text copied to clipboard."* / *"Clipboard cleared."*

---

## 3. Capability Registry & Permissions Contract

| Capability ID | Tool Name | Risk Level | Permission Level | Read Only | Reversible |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `system.open_application` | `open_application` | `RISK_2` | `SAFE` | No | Yes |
| `system.application_status` | `application_status` | `RISK_1` | `SAFE` | Yes | N/A |
| `filesystem.search_files` | `search_files` | `RISK_1` | `SAFE` | Yes | N/A |
| `system.read_clipboard` | `read_clipboard` | `RISK_1` | `SAFE` | Yes | N/A |
| `system.write_clipboard` | `write_clipboard` | `RISK_2` | `SAFE` | No | Yes |

All five tools are registered directly into:
1. `DEFAULT_TOOL_METADATA` (`src/tools/registry.py`)
2. `AstraAgent._register_default_tools` (`src/brain/agent.py`)
3. `ToolVerifier` pre- and post-execution validation pipelines (`src/execution/verifier.py`)

---

## 4. Voice & Speech Synthesis Pipeline

When desktop control tools execute, responses flow seamlessly into ASTRA's natural voice pipeline:

1. **Tool Result Message**: Structured, human-readable confirmation generated by tool.
2. **Agent Context Builder**: Result recorded in conversational turn context.
3. **Text Sanitization (`sanitize_text_for_speech`)**:
   - Strips code blocks, markdown punctuation, file paths, and raw symbols.
   - Cleans formatting for natural prosody.
4. **TTS Engine (`ElevenLabsProvider` / `pyttsx3`)**:
   - Streamed or buffered audio played through speaker device.

---

## 5. Verification & Testing Summary

Comprehensive automated unit and integration tests located in `tests/test_desktop_control.py`:

- **Application Launcher**:
  - Allowlist acceptance (`notepad`, `calculator`, `settings`, `browser`, `vscode`, `paint`).
  - Strict rejection of unallowlisted apps.
  - Safe argument list execution (`shell=False`).
  - Native `os.startfile` execution for `ms-settings:`.
  - Process existence and PID capture verification.
  - Honest missing executable failure (`NOT_FOUND`).
  - Already-running process detection via `psutil`.
- **File and Folder Search**:
  - Approved root directory acceptance (`Downloads`, `Documents`, `Desktop`, sandbox).
  - Strict rejection of system directories and paths outside approved roots (`DENIED`).
  - Strict depth bounding (files beyond depth 3 ignored).
  - Strict result capping ($\le 20$ results).
  - Timeout enforcement ($\le 5.0$s).
  - Tolerance of inaccessible directories (`PermissionError`).
  - Metadata-only verification (no sensitive contents exposed).
- **Clipboard Operations**:
  - Read and write accuracy.
  - Secret redaction test (verifies `sk_live_...` and `password` sanitized to `[REDACTED]`).
  - Empty clipboard handling.
  - Parameter validation and non-string rejection.
- **System Integration**:
  - `AstraAgent` capability registration verification.
  - `ToolExecutor` pipeline verification.
  - Speech sanitization verification.
