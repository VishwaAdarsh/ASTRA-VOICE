# ASTRA V2 — Master Architecture Specification

**Document Version:** 2.0.0  
**Phase:** V2-01 (Architecture & Repository Foundation)  
**Target Operating System:** Windows 10 / Windows 11  
**Single Source of Truth:** Canonical ASTRA V2 Specification  

---

## 1. System Overview & Core Philosophy

ASTRA is an intelligent, voice-first personal computer assistant built for Windows. It unites high-accuracy local speech processing, hands-free wake-word detection, controlled multi-step LLM orchestration (Google Gemini), OS tool execution with strict allowlists, and a presentation layer built with Google's Stitch Design System (React 19 / Tailwind CSS).

### Core Architectural Axioms
1. **Separation of Cognition and Execution:** The cognitive brain (LLM) decides *intent* and *tool arguments*, but never directly executes shell strings or modifies the operating system. Execution is strictly handled by strongly typed, verified tools.
2. **Explicit Verification Over Assumption:** Attempting an operation does not constitute success. Every side effect (file creation, process launch, automation trigger) must be authoritatively verified by `ToolVerifier`.
3. **Strict Directional Dependencies:** Higher-level interfaces depend on lower-level infrastructure, never the inverse:
   $$\text{Core} \longrightarrow \text{Infrastructure} \longrightarrow \text{Capabilities} \longrightarrow \text{Cognition} \longrightarrow \text{Interfaces}$$
4. **Offline-First Audio & Local Privacy:** Voice detection, acoustic energy analysis, hands-free wake-word listening ("Hey ASTRA"), and Text-to-Speech occur 100% locally on the device without streaming raw ambient microphone audio to cloud APIs.

---

## 2. Canonical Architecture Diagram

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                              INTERFACES LAYER                                │
│                                                                              │
│   ┌──────────────────────────┐    ┌──────────────────────────────────────┐   │
│   │   AstraWebWindow         │    │       Interactive Terminal CLI       │   │
│   │   (PySide6 WebEngine)    │    │          (src/interfaces/cli)        │   │
│   └────────────┬─────────────┘    └──────────────────┬───────────────────┘   │
│                │ HTTP / WS                           │ Python Calls          │
└────────────────┼─────────────────────────────────────┼───────────────────────┘
                 ▼                                     ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                          API & COMMUNICATION LAYER                           │
│                                                                              │
│   FastAPI REST Application  │  Starlette WebSocket Event Bus                 │
│   Endpoints: /command, /tasks, /automations, /memory, /vision, /voice        │
│   Secret Redaction Filter (`SecretRedactionFilter`)                          │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           CORE RUNTIME & LIFECYCLE                           │
│                                                                              │
│   SystemLifecycle (Startup/Shutdown) │ Config Manager (.env hierarchy)       │
│   HealthManager (Subsystem telemetry)│ CrashRecoveryManager                  │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                          AGENT & COGNITIVE ENGINE                            │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │ AstraAgent (Multi-Step Orchestration Loop, Max Iterations = 5)       │   │
│   └──────────┬──────────────────────┬────────────────────────┬───────────┘   │
│              ▼                      ▼                        ▼               │
│      ┌──────────────┐       ┌──────────────┐         ┌───────────────┐       │
│      │  LLMClient   │       │ContextManager│         │Intent Fallback│       │
│      └───────┬──────┘       └──────────────┘         └───────────────┘       │
│              ▼                                                               │
│      ┌──────────────┐                                                        │
│      │GeminiProvider│ (google-genai SDK, gemini-3.6-flash, schema cache)     │
│      └──────────────┘                                                        │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              CAPABILITY LAYER                                │
│                                                                              │
│   ┌───────────────────────┐  ┌───────────────────────┐  ┌────────────────┐   │
│   │  ToolRegistry         │  │ VoiceManager          │  │ VisionManager  │   │
│   │  - Filesystem Tools   │  │ - MicrophoneManager   │  │ - ScreenCapture│   │
│   │  - Application Tools  │  │ - WakeWordListener    │  │ - OCRProvider  │   │
│   │  - System Tools       │  │ - SpeechRecognition   │  │ - VisualContext│   │
│   │  - Web Tools          │  │ - Pyttsx3 SAPI5 TTS   │  └────────────────┘   │
│   └──────────┬────────────┘  └───────────────────────┘                       │
│              │                                                               │
│   ┌──────────▼────────────┐  ┌───────────────────────┐  ┌────────────────┐   │
│   │  TaskManager          │  │ AutomationManager     │  │ MemoryManager  │   │
│   │  - Goal Decomposition │  │ - Scheduler (Cron)    │  │ - Semantic DB  │   │
│   │  - Dependency Graph   │  │ - Quiet Hours         │  │ - Policies     │   │
│   └───────────────────────┘  └───────────────────────┘  └────────────────┘   │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                      EXECUTION & SECURITY INFRASTRUCTURE                     │
│                                                                              │
│   PermissionManager (SAFE / CONFIRM_REQUIRED / ADMIN)                        │
│   SecurityAuditor (Input validation, path traversal defense)                 │
│   PromptInjectionDefense (Delimiter isolation)                               │
│   ToolExecutor (Subprocess and OS operations)                                │
│   ToolVerifier (Post-execution file/process confirmation)                    │
│   SQLite Database (data/astra_memory.db)                                     │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Subsystem Specifications

### 3.1 Entry Points
- **Canonical Launcher (`main.py`):** The single production entry point. Initializes runtime lifecycle, configures port binding, launches background API/WebSocket server, initializes hands-free voice detection, and displays the `AstraWebWindow` desktop GUI.
- **Legacy Compatibility (`src/main.py`):** Retained strictly for backward compatibility with CLI scripts. Emits a notice directing users to `main.py`.

### 3.2 User Interface
- **Primary Production UI:** React 19 single-page application built with Vite and Tailwind CSS (`Astra voice UI/`), pre-compiled into `Astra voice UI/dist` and served statically by FastAPI. Embedded natively in Windows through PySide6's `QWebEngineView` (`AstraWebWindow`).
- **Dynamic Port Connection:** The frontend `AstraApiClient` detects `window.location.host` dynamically. In production WebEngine mode, it binds directly to whatever local port FastAPI binds (8000–8020), eliminating desynchronization.

### 3.3 Provider Architecture (Real vs. Mock)
All capabilities requiring external services or hardware adhere to the Provider Factory Pattern:
- **Explicit Resolution:** Providers must be explicitly declared via configuration (`LLM_PROVIDER`, `STT_PROVIDER`, `TTS_PROVIDER`, `WEB_SEARCH_PROVIDER`, `VISION_PROVIDER`, `OCR_PROVIDER`).
- **Zero Silent Fallback:** If an unrecognized or unavailable real provider is requested, factories explicitly raise exceptions rather than silently degrading to mock mode.
- **Production Defaults:**
  - LLM: `GeminiProvider` (`gemini-3.6-flash`).
  - STT: `SpeechRecognitionSTTProvider`.
  - TTS: `Pyttsx3TTSProvider` (SAPI5 native Windows).
  - Search: `DuckDuckGoSearchProvider`.
  - Wake Word: `LocalWakeWordDetector` (offline acoustic energy matching).

### 3.4 Execution & Verification Pipeline
When the Agent selects a tool, execution flows through the authoritative security pipeline:
1. `ToolRegistry.get_tool(tool_name)` validates schema and parameters.
2. `PermissionManager.check_permission(tool, parameters)` verifies user permission level (`SAFE`, `CONFIRM_REQUIRED`, `ADMIN`).
3. `SecurityAuditor` validates paths, command safety, and input sanitization.
4. `ToolExecutor.execute(request)` runs the tool logic.
5. `ToolVerifier.verify(result)` inspects the actual operating system state to confirm success before reporting back to the agent.

---

## 4. Architectural Decision Records (ADRs)

Key architectural choices made for ASTRA V2 are formally recorded under `docs/adr/`:
- **[ADR-001](adr/ADR-001-canonical-entrypoint.md):** Canonical Application Entry Point (`main.py`).
- **[ADR-002](adr/ADR-002-canonical-ui.md):** Canonical UI Architecture (React Stitch UI via PySide6 WebEngine).
- **[ADR-003](adr/ADR-003-provider-separation.md):** Strict Provider Separation and Prohibition of Silent Mock Fallbacks.
- **[ADR-004](adr/ADR-004-project-structure.md):** Architectural Layering and Dependency Direction.
