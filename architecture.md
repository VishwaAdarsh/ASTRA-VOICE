# ASTRA — Master Architecture Blueprint

```text
================================================================================
                                 A S T R A
                      Personal AI Computer Assistant
                      
               Understand. Think. Act. Remember. See. Plan. Proact. Harden.
================================================================================
```

* **Document Version:** 2.10.0
* **Status:** Master Blueprint / Single Source of Truth
* **Current Implementation:** Phase 11 (Security, Reliability & Production Hardening Completed)
* **Target Operating System:** Windows 10 / Windows 11











---

## 1. Overview & Identity

**ASTRA** is a long-term personal AI computer assistant designed specifically for Windows. Its overarching goal is to evolve into a reliable, voice-first personal operating system assistant capable of understanding natural language, performing authorized computer operations, managing files, controlling desktop software, conducting web research, maintaining useful personal memory, and assisting with daily user productivity.

### Identity Core
```text
Understand. Think. Act. Remember.
```

### Core Identity Principles
ASTRA is NOT an unrestricted autonomous bot or malware-like shell runner. ASTRA is designed around four key operational pillars:
* **Capable:** Executes meaningful, high-value operating system and productivity actions.
* **Reliable:** Verifies execution outcomes instead of assuming success; fails gracefully under error conditions.
* **Observable:** Maintains an explicit, human-auditable trail of commands, intents, tool selections, and results.
* **Permission-Aware:** Operates under strict user-defined security policies and confirmation boundaries.

---

## 2. Permanent Architectural Design Principles

The following fifteen design principles govern all existing and future development of Project ASTRA:

### 2.1 Modular Architecture
Every major capability must exist as an independent, loosely coupled subsystem with clear module boundaries. Components communicate through explicit Data Transfer Objects (DTOs) and defined interfaces.

### 2.2 Separation of Reasoning and Execution
The reasoning layer (Brain/LLM) decides *intent* and *parameters*, but must **never** directly execute arbitrary operating-system commands. Actual execution is strictly delegated to registered, allowlisted tools.

```text
AI Reasoning → Structured Tool Request → Permission Check → Tool → Operating System
```

### 2.3 Security by Default
* No arbitrary shell execution (e.g., `run_any_command()`, `eval()`, `exec()` are strictly prohibited).
* Every executable capability must be registered in the central `ToolRegistry`.
* Security policy applies uniformly regardless of input channel (Voice, CLI, GUI, API).

### 2.4 Verification Architecture
ASTRA must distinguish between *Requested*, *Executed*, and *Verified*. ASTRA must never falsely claim an operation succeeded without empirical runtime verification.

### 2.5 Provider Independence
Subsystems depending on external vendors or hardware (LLM engines, Speech-To-Text, Text-To-Speech, Web Search APIs, Vector Databases) must be isolated behind abstract provider interfaces to allow zero-code-change provider swapping.

### 2.6 Observability & Traceability
All key system state transitions, command receipts, intent recognitions, tool selections, permission checks, tool results, and errors must be recorded in structured logs without logging secrets or raw user audio.

### 2.7 Graceful Failure Isolation
A failure in a single tool, external provider, or voice peripheral must never crash the core assistant engine. Failures are caught, translated into user-friendly responses, and logged for diagnostics.

### 2.8 Human Control & Authority
The user remains the ultimate authority. Sensitive, destructive, or high-risk actions require explicit user confirmation before execution.

### 2.9 Incremental Layered Development
Capabilities are added phase-by-phase. Higher-level layers (Voice, LLM, Vision, Autonomous Tasks) build upon lower-level foundations without rewriting core infrastructure.

### 2.10 Testability & Mockability
Every subsystem must be independently testable via unit and integration tests. Hardware devices (microphones, speakers) and external APIs (LLM, STT, Web Search) must be fully mockable.

### 2.11 Controlled Memory Access
User memory is structured, observable, editable, and deletable by the user. Memory storage must strictly enforce user privacy.

### 2.12 Deterministic Execution for Deterministic Tasks
Where deterministic rule matching or static OS APIs suffice, ASTRA prefers deterministic logic over non-deterministic LLM calls for speed, predictability, and safety.

### 2.13 UI & Input Independence
The core engine (`AstraAgent`) is completely decoupled from user interfaces. UI applications (CLI, PySide6 Desktop GUI, Voice Mode) consume core events and state without modifying core business logic.

### 2.14 Zero Hardcoded Secrets
API keys, credentials, and sensitive configurations must strictly reside in environment variables (`.env`). Secrets must never be committed to repository code or exposed in log outputs.

### 2.15 Single Execution Path
Command parsing, routing, permission validation, execution, and verification follow **one single execution path** across all user input channels.

---

## 3. Master High-Level Architecture Blueprint

```text
                               ┌─────────────────────────┐
                               │          USER           │
                               │  (Voice / Text / UI)    │
                               └────────────┬────────────┘
                                            │
                                            ▼
                               ┌─────────────────────────┐
                               │       INPUT LAYER       │
                               │  - CLI / Text Input     │
                               │  - Voice Stream (Phase 2)│
                               │  - Desktop GUI (Phase 3)│
                               └────────────┬────────────┘
                                            │ Command String / Event
                                            ▼
                               ┌─────────────────────────┐
                               │      CONTEXT LAYER      │
                               │  - Session History      │
                               │  - Active App / Window  │
                               │  - User Preferences     │
                               └────────────┬────────────┘
                                            │
                                            ▼
                               ┌─────────────────────────┐
                               │       ASTRA BRAIN       │
                               │  - Intent Recognition   │
                               │  - Rule / LLM Parser    │
                               │  - Parameter Extractor  │
                               └────────────┬────────────┘
                                            │ Intent / Plan
                                            ▼
                               ┌─────────────────────────┐
                               │     ACTION PLANNER      │
                               │  - Intent Router        │
                               │  - Tool Selection       │
                               │  - Task Decomposition   │
                               └────────────┬────────────┘
                                            │ ToolRequest
                                            ▼
                               ┌─────────────────────────┐
                               │    SECURITY / POLICY    │
                               │  - PermissionManager    │
                               │  - Level Check (SAFE)   │
                               │  - User Confirmation    │
                               └────────────┬────────────┘
                                            │ Authorized ToolRequest
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                       TOOL LAYER                                        │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────────┐  │
│  │ Applications    │ │ Filesystem      │ │ Browser         │ │ System Information      │  │
│  │ (calc, notepad) │ │ (downloads, etc)│ │ (youtube, etc)  │ │ (OS, RAM, Python)       │  │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘ └─────────────────────────┘  │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────────┐  │
│  │ Web Search (P6) │ │ Memory (P7)     │ │ Vision (P8)     │ │ Tasks/Notes (P9)        │  │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘ └─────────────────────────┘  │
└───────────────────────────────────────────┬─────────────────────────────────────────────┘
                                            │
                                            ▼
                               ┌─────────────────────────┐
                               │    EXECUTION ENGINE     │
                               │  - ToolExecutor         │
                               │  - Exception Isolation  │
                               │  - Pre/Post Checks      │
                               └────────────┬────────────┘
                                            │
                                            ▼
                               ┌─────────────────────────┐
                               │    VERIFICATION LAYER   │
                               │  - ToolVerifier         │
                               │  - Pre/Post Validation  │
                               │  - Status Determination │
                               └────────────┬────────────┘
                                            │ ToolResult
                                            ▼
                               ┌─────────────────────────┐
                               │     RESPONSE LAYER      │
                               │  - Response Formatter   │
                               │  - Text Output (CLI/UI) │
                               │  - TTS Engine (Phase 2) │
                               └────────────┬────────────┘
                                            │
                                            ▼
                               ┌─────────────────────────┐
                               │   LOGGING & DIAGNOSTICS │
                               │  - Central Logger       │
                               │  - data/logs/astra.log  │
                               └─────────────────────────┘
```

---

## 4. Detailed Layer Specifications

### 4.1 Input Layer (`src/interfaces/`, `src/voice/`)
* **Responsibility:** Captures user interaction through text, microphone stream, GUI events, or future hotkeys.
* **Output:** Normalizes all inputs into a standard `Command` model containing `raw_text`, `normalized_text`, and timestamp.
* **Channel Isolation:** Input adapters do not execute business logic; they immediately hand off the normalized command to `AstraAgent`.

### 4.2 Context Layer (`src/brain/`, `src/memory/`)
* **Responsibility:** Maintains short-term conversational context, environment state, active application focus, and user preferences.
* **Context vs Memory:** Distinguishes temporary transient session state from persistent long-term vector/database memory.

### 4.3 Brain Layer (`src/brain/`)
* **Responsibility:** Determines what the user wants to accomplish.
* **Phase 1 Implementation:** Abstract `IntentRecognizer` interface with deterministic `RuleBasedIntentRecognizer`.
* **Phase 4 Target:** `LLMIntentRecognizer` for natural language reasoning, structured schema extraction, and open-domain understanding.

### 4.4 Action Planning Layer (`src/brain/router.py`)
* **Responsibility:** Maps recognized `Intent` objects into concrete, structured `ToolRequest` instances specifying target `tool_name` and extracted parameters.
* **Scope:** Single-tool routing in Phase 1; multi-step task decomposition in Phase 9.

### 4.5 Security & Policy Layer (`src/security/`)
* **Responsibility:** Enforces permission policies (`SAFE`, `CONFIRM`, `RESTRICTED`) and manages interactive user confirmation prompts before execution.
* **Authority:** Operates independently of the input source. No interface or LLM prompt can bypass this layer.

### 4.6 Tool Layer (`src/tools/`)
* **Responsibility:** Defines all approved executable actions as subclasses of `BaseTool`.
* **Registry Enforcement:** Central `ToolRegistry` maintains the canonical list of approved tools. Execution of unregistered tools is blocked.

### 4.7 Execution Engine (`src/execution/executor.py`)
* **Responsibility:** Manages the tool invocation lifecycle: Tool Lookup → Pre-Verification → Permission Check → User Confirmation → Execution → Exception Isolation → Post-Verification.

### 4.8 Verification Layer (`src/execution/verifier.py`)
* **Responsibility:** Performs pre-checks (verifying target file paths, application allowlist status, URL formats) and post-checks (validating process launch and output data integrity).

### 4.9 Response Layer (`src/interfaces/`, `src/voice/`)
* **Responsibility:** Formats structured `ToolResult` data into natural human-readable text and routes response to CLI, Desktop UI, or TTS engine.

### 4.10 Logging & Memory Layer (`src/core/logger.py`, `data/logs/`)
* **Responsibility:** Stores dual log outputs (console + file log `data/logs/astra.log`) recording all pipeline steps (`COMMAND_RECEIVED`, `INTENT_DETECTED`, `TOOL_SELECTED`, `PERMISSION_CHECK`, `TOOL_EXECUTION`, `TOOL_RESULT`).

---

## 5. Tool Architecture & Registry Specification

### 5.1 Tool Schema Model
Every executable capability derives from `BaseTool`:

```python
class BaseTool(ABC):
    name: str
    description: str
    permission_level: PermissionLevel = PermissionLevel.SAFE

    @abstractmethod
    def validate(self, parameters: dict[str, Any]) -> bool:
        """Validate parameter schema and safe bounds."""
        pass

    @abstractmethod
    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        """Perform action and return structured result."""
        pass
```

### 5.2 Tool Registry Rules
1. **Zero Dynamic Execution:** Only tools explicitly registered in `ToolRegistry` can be called.
2. **Name Uniqueness:** Tool names must be unique lowercase identifiers (e.g., `open_application`, `open_folder`).
3. **Strict Validation:** Tools must validate all incoming parameters before invoking OS APIs.

### 5.3 Extension Categories Roadmap
* **Phase 1 (Implemented):** Applications, Filesystem, Browser, System Information.
* **Phase 5:** Advanced File Management, Window Control, Process Manager.
* **Phase 6:** Web Search, Web Fetch, Page Summarizer.
* **Phase 7:** Memory Store, Memory Query, Memory Delete.
* **Phase 8:** Screen Capture, Document OCR, Image Analyzer.
* **Phase 9:** Calendar, Reminders, Notes, Task Manager.

---

## 6. Execution & Verification Lifecycle

```text
User Input → Command → Intent → ToolRequest
                                    │
                                    ▼
                        ┌───────────────────────┐
                        │   ToolRegistry.get()  │
                        └───────────┬───────────┘
                                    │ Tool Instance
                                    ▼
                        ┌───────────────────────┐
                        │ Pre-Execution Check   │
                        │ (ToolVerifier)        │
                        └───────────┬───────────┘
                                    │ Valid Pre-Conditions
                                    ▼
                        ┌───────────────────────┐
                        │ Permission Check      │
                        │ (PermissionManager)   │
                        └───────────┬───────────┘
                                    │ Authorized
                                    ▼
                        ┌───────────────────────┐
                        │  Confirmation Prompt  │
                        │  (if level == CONFIRM)│
                        └───────────┬───────────┘
                                    │ Approved
                                    ▼
                        ┌───────────────────────┐
                        │  Parameter Validation │
                        │  (Tool.validate())    │
                        └───────────┬───────────┘
                                    │ Valid Parameters
                                    ▼
                        ┌───────────────────────┐
                        │     Tool.execute()    │
                        └───────────┬───────────┘
                                    │ Raw Result
                                    ▼
                        ┌───────────────────────┐
                        │ Post-Execution Check  │
                        │ (ToolVerifier)        │
                        └───────────┬───────────┘
                                    │
                                    ▼
                               ToolResult
```

### Verification States
* **Requested:** Intent recognized and `ToolRequest` created.
* **Executed:** Tool method invoked without unhandled crash.
* **Verified:** `ToolVerifier` confirms target pre/post conditions (e.g., process started, folder exists, output collected).

---

## 7. Future Subsystem Architectures (High-Level Blueprints)

### 7.1 Voice Subsystem Architecture (Phase 2 Blueprint)
```text
Microphone Stream → MicrophoneManager → VAD (Silence Detector) → STT Provider → Transcript
                                                                                     │
                                                                                ASTRA Core
                                                                                     │
Speakers ← Sound Output ← TTS Engine ← Response Formatter ← ToolResult ←─────────────┘
```
* **Isolation:** Voice subsystem converts audio to text and text to audio; it contains zero tool/OS execution logic.
* **Provider Abstraction:** `SpeechToTextProvider` and `TextToSpeechProvider` abstract vendor APIs (e.g., Windows SAPI5 / pyttsx3, SpeechRecognition, Whisper).
* **Voice State Machine:** `IDLE` → `LISTENING` → `PROCESSING` → `SPEAKING` → `IDLE` (or `ERROR`).

### 7.2 Desktop UI Architecture (Phase 3 Blueprint)
* **Technology:** PySide6 (Qt for Python) featuring modern Fluent design aesthetics.
* **Event-Driven Architecture:** UI subscribes to core lifecycle and execution events (`VOICE_STATE_CHANGED`, `COMMAND_RECEIVED`, `TOOL_EXECUTED`).
* **Non-Blocking Core:** Long-running tools and audio tasks run on worker threads, keeping the GUI UI thread 100% responsive.

### 7.3 LLM Reasoning Architecture (Phase 4 Blueprint)
* **Provider Interface:** `LLMProvider` abstract class with concrete adapters for OpenAI, Anthropic, Ollama, and local models.
* **Structured Output:** Enforces strict JSON Schema for tool selection and argument parsing.
* **Fallback Chain:** Falls back to deterministic rule matching if LLM network call fails.

### 7.4 Memory Subsystem Architecture (Phase 7 Blueprint)
* **Short-Term Memory:** In-memory ring buffer of recent turn interactions.
* **Long-Term Memory:** Local SQLite database storing user facts and preferences.
* **Semantic Memory:** Local vector database (e.g., ChromaDB / LanceDB) with local embedding models for semantic document & preference retrieval.

### 7.5 Web Intelligence Subsystem Architecture (Phase 6 Blueprint)
* **Search Engine Abstraction:** `WebSearchProvider` returning structured search results.
* **Safe Scraper:** Read-only HTML to Markdown parser for extracting text content from authorized web pages.

### 7.6 Vision Subsystem Architecture (Phase 8 Blueprint)
* **Screen Inspector:** Captures active desktop screen or window bounded regions.
* **Vision Model Interface:** `VisionProvider` analyzing UI layouts, screenshots, and visual documents.

---

## 8. Security, Permission & Risk Model

### 8.1 Risk Classification Scale

| Risk Level | Category Name | Description | Examples | Handling Policy |
| :--- | :--- | :--- | :--- | :--- |
| **Level 0** | Informational | Read-only non-sensitive system queries | System info, time check | Allowed automatically (`SAFE`) |
| **Level 1** | Safe Operations | Standard desktop actions on allowlisted targets | Open calculator, open Downloads folder, open YouTube | Allowed automatically (`SAFE`) |
| **Level 2** | Data Modification | Creating, renaming, moving user files or writing notes | Create text note, move file to folder | Requires validation (`SAFE` / `CONFIRM`) |
| **Level 3** | Destructive / External | Deleting files, modifying system settings, sending data | Delete file, change network setting | Explicit confirmation required (`CONFIRM`) |
| **Level 4** | Highly Sensitive | Administrative tasks, secret access, financial actions | Format disk, export API keys, administrative commands | Strictly blocked in normal mode (`RESTRICTED`) |

### 8.2 Secret Management Policy
* All API keys, environment settings, and credentials must be loaded via `Config` from `.env`.
* `.env` is listed in `.gitignore` and must never be committed to repository source control.
* Raw secrets are scrubbed before writing log entries to `data/logs/astra.log`.

---

## 9. Error Taxonomy & Resilience Strategy

```text
AstraError (Base)
 ├── ConfigurationError
 ├── IntentRecognitionError
 ├── ToolError
 │    ├── ToolNotFoundError
 │    ├── InvalidParametersError
 │    └── ToolExecutionError
 ├── PermissionDeniedError
 ├── VerificationError
 ├── VoiceError (Phase 2)
 ├── LLMError (Phase 4)
 └── MemoryError (Phase 7)
```

### Resilience Rules
1. **No Fatal Tool Crashes:** Unhandled tool exceptions are caught by `ToolExecutor` and returned as `ToolResult(status=ExecutionStatus.FAILED)`.
2. **Provider Failover:** If an external network API fails, ASTRA gracefully notifies the user and returns to `IDLE` state.
3. **State Self-Healing:** The system state machine automatically resets to `IDLE` after handling any error condition.

---

## 10. Database & Data Storage Strategy

* **Phase 1 Storage:** Plain-text structured file logging under `data/logs/astra.log`.
* **Phase 7 Storage:** Embedded `SQLite` database under `data/database/astra.db` storing:
  - User Settings & Preferences
  - Tool Execution History & Audit Logs
  - Persistent Memory Entries
* **Vector Storage (Phase 7):** Embedded local vector storage for semantic retrieval. No heavy cloud database requirements.

---

## 11. Target Repository Structure

```text
ASTRA/
├── README.md                  # Project overview and usage guide
├── architecture.md            # Master Blueprint (Single Source of Truth)
├── requirements.txt           # Dependency manifest
├── .env.example               # Environment variables template
├── .gitignore                 # Git ignore rules
│
├── src/
│   ├── __init__.py
│   ├── main.py                # Main CLI entry point
│   │
│   ├── core/                  # Core Infrastructure
│   │   ├── __init__.py
│   │   ├── config.py          # Central configuration & allowlists
│   │   ├── lifecycle.py       # System startup & shutdown
│   │   ├── exceptions.py      # Exception taxonomy
│   │   └── logger.py          # Central dual logger
│   │
│   ├── brain/                 # Intent Recognition & Reasoning
│   │   ├── __init__.py
│   │   ├── agent.py           # Core agent orchestrator
│   │   ├── intent.py          # IntentRecognizer & RuleBasedIntentRecognizer
│   │   ├── router.py          # Intent to ToolRequest router
│   │   └── models.py          # Domain data models & enums
│   │
│   ├── voice/                 # Voice Subsystem (Phase 2 Planned)
│   │   ├── __init__.py
│   │   ├── audio.py
│   │   ├── microphone.py
│   │   ├── vad.py
│   │   ├── stt.py
│   │   ├── tts.py
│   │   ├── session.py
│   │   ├── events.py
│   │   ├── models.py
│   │   └── manager.py
│   │
│   ├── tools/                 # Allowlisted Tool System
│   │   ├── __init__.py
│   │   ├── base.py            # BaseTool abstract class
│   │   ├── registry.py        # ToolRegistry
│   │   ├── applications.py    # open_application
│   │   ├── filesystem.py      # open_folder
│   │   ├── browser.py         # open_website
│   │   └── system.py          # system_information
│   │
│   ├── security/              # Security & Permission Layer
│   │   ├── __init__.py
│   │   ├── permissions.py     # PermissionManager
│   │   └── confirmation.py    # ConfirmationHandler
│   │
│   ├── execution/             # Tool Execution & Verification
│   │   ├── __init__.py
│   │   ├── executor.py        # ToolExecutor
│   │   └── verifier.py        # ToolVerifier
│   │
│   └── interfaces/            # User Interfaces
│       ├── __init__.py
│       └── cli.py             # Interactive Terminal CLI
│
├── tests/                     # Test Suite
│   ├── __init__.py
│   ├── test_intent.py
│   ├── test_router.py
│   ├── test_tools.py
│   ├── test_permissions.py
│   └── test_executor.py
│
└── data/
    └── logs/                  # Log storage
        └── .gitkeep
```

---

## 12. Complete Development Roadmap (Phases 0 to 12)

```text
Phase 0: Architecture & Foundation Blueprint  [COMPLETED]
   │
Phase 1: Foundation & Core Proof of Concept   [COMPLETED]
   │
Phase 2: Voice Intelligence Layer             [PLANNED NEXT]
   │
Phase 3: Modern Desktop UI (PySide6)          [PLANNED]
   │
Phase 4: LLM Brain Reasoning Upgrade          [PLANNED]
   │
Phase 5: Advanced File & Application Control  [PLANNED]
   │
Phase 6: Web Intelligence & Research Agent    [PLANNED]
   │
Phase 7: Memory & Personal Knowledge Base     [PLANNED]
   │
Phase 8: Vision & Screen Understanding        [PLANNED]
   │
Phase 9: Multi-Step Autonomous Task Planner   [PLANNED]
   │
Phase 10: Proactive Assistant & Automation    [PLANNED]
   │
Phase 11: Security Hardening & Reliability     [PLANNED]
   │
Phase 12: ASTRA 1.0 Production Release        [PLANNED]
```

### Phase Details

#### Phase 0 — Architecture & Foundation Blueprint
* **Status:** COMPLETED
* **Objective:** Establish master design blueprint and permanent engineering principles.

#### Phase 1 — Foundation & Core Proof of Concept (M0)
* **Status:** COMPLETED
* **Objective:** Build modular core engine, allowlisted tool registry (`open_application`, `open_folder`, `open_website`, `system_information`), rule-based intent recognition, permission manager, executor, verifier, dual logging, CLI interface, and unit test suite.

#### Phase 2 — Voice Intelligence Layer
* **Status:** PLANNED NEXT
* **Objective:** Introduce microphone capture, VAD, STT provider interface, TTS provider interface, voice state machine, and voice session manager without modifying Phase 1 core logic.

#### Phase 3 — Modern Desktop UI
* **Status:** PLANNED
* **Objective:** Build PySide6 Fluent desktop interface featuring voice orb, activity stream, system status, and settings panel.

#### Phase 4 — LLM Brain Reasoning Upgrade
* **Status:** PLANNED
* **Objective:** Add provider-independent LLM reasoning engine for complex natural language parsing, dynamic parameter extraction, and context-aware decision making.

#### Phase 5 — Advanced File & Application Control
* **Status:** PLANNED
* **Objective:** Support file search, file creation/manipulation, window focus switching, process inspection, and safe system settings controls.

#### Phase 6 — Web Intelligence & Research Agent
* **Status:** PLANNED
* **Objective:** Integrate safe web search provider, webpage content summarizer, and multi-source research extraction.

#### Phase 7 — Memory & Personal Knowledge Base
* **Status:** PLANNED
* **Objective:** Implement SQLite database storage, local vector database embeddings, short/long-term memory retrieval, and user memory manager.

#### Phase 8 — Vision & Screen Understanding
* **Status:** PLANNED
* **Objective:** Add desktop screenshot capture, visual UI element inspection, document OCR, and image analysis.

#### Phase 9 — Multi-Step Autonomous Task Planner
* **Status:** PLANNED
* **Objective:** Enable multi-tool task decomposition, execution plan tracking, step-by-step verification, and recovery.

#### Phase 10 — Proactive Assistant & Automation
* **Status:** PLANNED
* **Objective:** Introduce background reminder monitoring, daily activity summaries, and authorized productivity task scheduling.

#### Phase 11 — Security Hardening & Reliability
* **Status:** PLANNED
* **Objective:** Comprehensive penetration audit, sandbox boundary validation, rate limiting, and failure recovery stress testing.

#### Phase 12 — ASTRA 1.0 Production Release
* **Status:** PLANNED
* **Objective:** Final packaging, installer creation, documentation polish, and production deployment.

---

## 13. Current Implementation Status vs Planned Subsystems

| Component / Subsystem | Current Status | Implemented Phase | Target Phase |
| :--- | :--- | :--- | :--- |
| **Core Lifecycle & Config** | Fully Implemented | Phase 1 | Phase 1 |
| **Central Logger & Exception Taxonomy** | Fully Implemented | Phase 1 | Phase 1 |
| **Domain Models & Enums** | Fully Implemented | Phase 1 | Phase 1 |
| **Rule-Based Intent Recognizer** | Fully Implemented | Phase 1 | Phase 1 |
| **Intent Router** | Fully Implemented | Phase 1 | Phase 1 |
| **Tool Registry & BaseTool** | Fully Implemented | Phase 1 | Phase 1 |
| **Allowlisted App Tool (`open_application`)** | Fully Implemented | Phase 1 | Phase 1 |
| **Allowlisted Folder Tool (`open_folder`)** | Fully Implemented | Phase 1 | Phase 1 |
| **Allowlisted Website Tool (`open_website`)** | Fully Implemented | Phase 1 | Phase 1 |
| **System Info Tool (`system_information`)** | Fully Implemented | Phase 1 | Phase 1 |
| **Permission Manager (`SAFE`, `CONFIRM`, `RESTRICTED`)** | Fully Implemented | Phase 1 | Phase 1 |
| **Tool Executor & Pre/Post Verifier** | Fully Implemented | Phase 1 | Phase 1 |
| **Interactive Terminal CLI (`src/interfaces/cli.py`)** | Fully Implemented | Phase 1 | Phase 1 |
| **Pytest Suite (99 Tests Passing)** | Fully Implemented | Phase 1 - 9 | Phase 1 - 9 |
| **Voice Subsystem (Microphone, STT, TTS, VAD)** | Fully Implemented | Phase 2 | Phase 2 |
| **PySide6 Desktop GUI (`src/ui/`)** | Fully Implemented | Phase 3 | Phase 3 |
| **LLM Brain Reasoning Engine (`src/brain/llm/`)** | Fully Implemented | Phase 4 | Phase 4 |
| **Advanced File & Computer Control (`src/tools/`)** | Fully Implemented | Phase 5 | Phase 5 |
| **Web Intelligence & Research Engine (`src/tools/web/`)** | Fully Implemented | Phase 6 | Phase 6 |
| **Memory, Personal Context Subsystem (`src/memory/`)** | Fully Implemented | Phase 7 | Phase 7 |
| **Vision, Screen Understanding Engine (`src/vision/`)** | Fully Implemented | Phase 8 | Phase 8 |
| **Autonomous Task Execution Engine (`src/task/`)** | Fully Implemented | Phase 9 | Phase 9 |
| **Proactive Assistant & Automation (`src/automation/`)** | Fully Implemented | Phase 10 | Phase 10 |
| **Security, Reliability & Hardening (`src/security/`, `src/core/`)** | Fully Implemented | Phase 11 | Phase 11 |




---

## 14. Minimum Viable Product (MVP) Definition

The **ASTRA MVP** is defined as the completion of **Phases 1 through 4 & 7**:

```text
ASTRA MVP Capabilities:
 [x] Text CLI interaction (Phase 1)
 [x] Controlled application, folder, website, and system info tools (Phase 1)
 [x] Security permissions & execution verification (Phase 1)
 [ ] Voice interaction via microphone & TTS (Phase 2)
 [ ] Modern PySide6 Desktop GUI (Phase 3)
 [ ] LLM-powered natural language intent recognition & tool routing (Phase 4)
 [ ] Basic persistent short/long term user memory (Phase 7)
```

---

## 15. Future ASTRA Capability Map

```text
                                  ASTRA ASSISTANT
                                         │
        ┌───────────────────┬────────────┴────────────┬───────────────────┐
        │                   │                         │                   │
        ▼                   ▼                         ▼                   ▼
  COMMUNICATION        INTELLIGENCE               COMPUTER CONTROL       WEB & RESEARCH
  - Terminal CLI      - Rule Engine (P1)          - App Launching (P1)   - URL Launcher (P1)
  - Voice Stream (P2) - LLM Reasoning (P4)        - Folder Navigation(P1)- Web Search (P6)
  - Desktop GUI (P3)  - Task Planner (P9)         - File Ops (P5)        - Page Summaries (P6)
                                                  - Window Control (P5)
                                                  - System Stats (P1)
                                                  - GUI Automation (P8)
                                         │
        ┌────────────────────────────────┴────────────────────────────────┐
        │                                                                 │
        ▼                                                                 ▼
     MEMORY                                                            VISION
  - Conversation Context                                          - Screen Analysis (P8)
  - Preference Database (P7)                                      - Document OCR (P8)
  - Vector Semantic Store (P7)                                    - Image Inspection (P8)
```

---

## 16. Non-Goals & Explicit System Boundaries

To preserve safety and project integrity, ASTRA will **NEVER** support or implement:

1. **Arbitrary Shell Execution:** Unrestricted system execution tools such as `run_any_command(cmd)` or `eval()` are permanently forbidden.
2. **Hidden / Background Recording:** Silent microphone audio recording or hidden uploads without visible user state indicators.
3. **Uncontrolled Financial Transactions:** Automatic credit card processing, unauthorized purchasing, or crypto wallet interactions.
4. **Credential Harvesting / Storage Bypass:** Storing raw passwords or attempting to bypass OS security/authentication boundaries.
5. **Self-Modifying System Core:** Uncontrolled code self-mutation or overwrite of core architecture files at runtime.
6. **Malware / Surveillance Behaviors:** Keylogging, secret background packet sniffing, or hidden telemetry collection.

---

## 17. Permanent Architectural Decision Records (ADRs)

### ADR-001: Python as Primary Implementation Language
* **Decision:** Use Python 3.10+ as the core language for ASTRA.
* **Rationale:** Unmatched library ecosystem for AI, speech processing, system APIs, cross-platform binding, and rapid modular prototyping.
* **Consequences:** Excellent developer productivity; performance-critical audio buffering must use native C-extensions (`numpy`, `sounddevice`, `pyttsx3`).

### ADR-002: PySide6 (Qt for Python) for Desktop GUI
* **Decision:** Adopt PySide6 for Phase 3 GUI implementation.
* **Rationale:** Provides native Windows Fluent aesthetics, hardware-accelerated UI rendering, thread-safe signal/slot mechanism, and robust desktop cross-platform support.
* **Alternatives Considered:** Tkinter (dated aesthetics), Electron (heavy memory overhead).

### ADR-003: Explicit Allowlisted Tool Execution Model
* **Decision:** All system actions must be encapsulated in concrete subclasses of `BaseTool` registered inside `ToolRegistry`.
* **Rationale:** Eliminates arbitrary shell vulnerability vectors; ensures strict argument validation and permission checks.

### ADR-004: Provider Abstraction Pattern
* **Decision:** Abstract vendor APIs (LLMs, STT, TTS, Web Search) behind abstract provider interfaces with factory pattern instantiation.
* **Rationale:** Prevents vendor lock-in; allows swapping cloud APIs with offline local models seamlessly.

### ADR-005: Security Policy & Permission Levels (`SAFE`, `CONFIRM`, `RESTRICTED`)
* **Decision:** Enforce three explicit security levels evaluated by `PermissionManager` prior to tool execution.
* **Rationale:** Ensures high-risk or destructive tools require human approval while non-destructive tools execute without unnecessary friction.

### ADR-006: Runtime Execution Verification Layer
* **Decision:** Implement `ToolVerifier` to conduct pre-execution condition checks and post-execution outcome validation.
* **Rationale:** Prevents reporting false success to the user when underlying system calls fail.

### ADR-007: SQLite as Initial Local Database Engine
* **Decision:** Use SQLite for local structured settings, history, and memory storage in Phase 7.
* **Rationale:** Zero-configuration, serverless, single-file storage native to Python standard library.

---

## 18. Architectural Quality Checklist

```text
Architecture Quality Verification:
 [x] Modular: Clear separation of core, brain, tools, security, execution, and interfaces.
 [x] Extensible: New tools can be registered without modifying core engine logic.
 [x] Testable: 25 automated unit/integration tests with mocks for external system calls.
 [x] Secure: Zero arbitrary shell execution; explicit tool allowlisting & permission levels.
 [x] Observable: Dual logging to console and data/logs/astra.log with secret scrubbing.
 [x] Provider-Independent: Abstract interfaces for Intent Recognizers, STT, TTS, and LLMs.
 [x] UI-Independent: Core engine (AstraAgent) is completely decoupled from CLI/GUI widgets.
 [x] Voice-Independent: Voice layer acts strictly as an I/O channel producing text commands.
 [x] Tool-Controlled: All actions encapsulated inside BaseTool subclasses.
 [x] Permission-Aware: Explicit PermissionManager checks before any execution.
 [x] Verification-Aware: Empirical runtime pre/post verification via ToolVerifier.
```
