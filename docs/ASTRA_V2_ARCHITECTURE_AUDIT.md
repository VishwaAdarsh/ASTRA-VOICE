# ASTRA V2 — Architecture & Repository Audit

**Document Version:** 1.0.0  
**Phase:** V2-01 (Architecture & Repository Foundation)  
**Status:** Canonical Audit Baseline  
**Scope:** Complete repository inspection across all 15 operational subsystems  

---

## 1. Current Architecture

ASTRA is an intelligent voice and desktop personal assistant for Windows 10/11. The project has evolved through 22 foundational development phases, culminating in a hybrid desktop architecture:
- **Presentation Layer:** Google Stitch Design System implemented in React 19 / Tailwind CSS, bundled with Vite and hosted inside a PySide6 QtWebEngineView window (`AstraWebWindow`).
- **Communication Layer:** FastAPI REST API + Starlette WebSocket server running on `uvicorn` inside a background thread, enabling bidirectional event streaming between the Python core and the React frontend.
- **Agent / Reasoning Layer (`src/brain/`):** Multi-step autonomous agent orchestrator (`AstraAgent`) powered by Google Gemini (`gemini-3.6-flash` via `google-genai` SDK) with tool schema generation, short-term context management, and deterministic rule-based fallback.
- **Capability Layer (`src/tools/`):** Strongly typed, allowlist-governed tools covering Windows application management, filesystem operations, web search/retrieval, system diagnostics, vision/screen understanding, memory storage, and task/automation scheduling.
- **Execution & Security Layer (`src/execution/`, `src/security/`):** Three-tier permission model (`PermissionManager`), pre-execution security auditor with secret redaction, and post-execution `ToolVerifier` confirming tangible OS state changes.
- **Voice Subsystem (`src/voice/`):** Single-device audio capture (`MicrophoneManager`), speech recognition (`SpeechRecognitionSTTProvider`), offline native Windows SAPI5 TTS (`Pyttsx3TTSProvider`), voice activity detection (`VoiceActivityDetector`), and local hands-free wake word engine (`LocalWakeWordDetector` for "Hey ASTRA").

---

## 2. Runtime Flow

The production execution lifecycle follows a unified unidirectional loop:

```text
[User Trigger: Wake Word ("Hey ASTRA") OR UI Microphone Click OR Text Input]
                                    │
                                    ▼
                         [VoiceSession / FastAPI]
                                    │
                       (Transcript / Command String)
                                    │
                                    ▼
                              [AstraAgent]
                                    │
                      [LLMClient → GeminiProvider]
                                    │
                ┌───────────────────┴───────────────────┐
                ▼                                       ▼
       [Direct Response]                       [Structured Tool Call]
                │                                       │
                │                           [ToolRegistry → PermissionManager]
                │                                       │
                │                              [ToolExecutor (Tool)]
                │                                       │
                │                              [ToolVerifier (Audit)]
                │                                       │
                │                        ┌──────────────┴──────────────┐
                │                        ▼                             ▼
                │                  [Multi-Step Next]          [Final Response Text]
                │                        │                             │
                └────────────────────────┼─────────────────────────────┘
                                         ▼
                             [AstraAgent Turn Complete]
                                         │
                         ┌───────────────┴───────────────┐
                         ▼                               ▼
                 [WebSocket Broadcast]             [Pyttsx3 TTS]
                         │                               │
                 (React Stitch UI)              (Windows Audio Speaker)
                         │                               │
                         └───────────────┬───────────────┘
                                         ▼
                     [Resume Wake-Word Listening / IDLE]
```

---

## 3. Entry Points

### Audit Findings
1. **Root `main.py` (Canonical Production Entrypoint):**
   - Parses CLI arguments (`--cli`, `--backend`, `--version`, `--debug`, `--port`).
   - Dynamically resolves available TCP ports (default 8000).
   - Starts `SystemLifecycle` and initializes `AstraAgent`.
   - Starts `VoiceManager` and hands-free wake-word listener (`LocalWakeWordDetector`).
   - Boots FastAPI + WebSocket server on background thread via `uvicorn`.
   - Boots PySide6 Qt application hosting `AstraWebWindow` (`QWebEngineView`), loading the React UI.
   - Registers OS signal handlers (`SIGINT`, `SIGTERM`) for coordinated graceful shutdown of server, audio streams, and background worker threads.

2. **`src/main.py` (Legacy Entrypoint):**
   - Originally launched the older native PySide6 desktop interface (`src/ui/app.py`).
   - Does not initialize the FastAPI/WebSocket server or the React Stitch UI.
   - **Resolution:** Isolated as legacy compatibility entrypoint with explicit deprecation notice and log warnings.

---

## 4. UI Architecture

ASTRA contains two UI implementations:
1. **React Stitch UI (`Astra voice UI/` - Canonical Production UI):**
   - React 19 + Vite 8 + Tailwind CSS 4 + Lucide Icons + Canvas Confetti.
   - Communicates with the backend exclusively through `AstraApiClient` (`src/services/api.js`) over REST (`/api/v1/*`) and WebSocket (`/api/v1/ws`).
   - Dynamic host resolution: detects `window.location.host` when embedded in QtWebEngine, eliminating hardcoded port desync.
   - Features rich status indicators (IDLE, LISTENING, PROCESSING, SPEAKING), prompt bar, visual waveform, task widgets, and memory viewers.
2. **Native PySide6 UI (`src/ui/` - Legacy/Reference UI):**
   - Native Qt widgets (`MainWindow`, `ThemeManager`, `components/`, `pages/`, `controllers/AppController`).
   - Directly binds Python signals to Qt controls.
   - **Resolution:** Retained in `src/ui/` for reference and headless testing, but designated secondary to the canonical WebEngine + React interface.

---

## 5. Backend & API Architecture

The backend API is implemented in `src/api/server.py` using FastAPI and Starlette WebSockets:
- **Factory Pattern:** `create_app(agent, voice_manager) -> FastAPI` mounts dependencies onto `app.state`.
- **Static File Serving:** Mounts `Astra voice UI/dist` at `/` to serve the production single-page React app.
- **REST Endpoints:**
  - `GET /api/v1/health`: System and subsystem health status.
  - `POST /api/v1/command`: Core text command execution path.
  - `GET /api/v1/tasks`, `POST /api/v1/tasks`: Task engine interaction.
  - `GET /api/v1/automations`, `POST /api/v1/automations`: Proactive automation triggers.
  - `GET /api/v1/memory`, `POST /api/v1/memory`: Long-term memory query and storage.
  - `GET /api/v1/vision`: Screen analysis context.
  - `GET /api/v1/settings`: Agent and provider configuration flags.
  - `POST /api/v1/voice/listen`, `POST /api/v1/voice/speak`, `POST /api/v1/voice/stop`: Voice hardware controls.
- **WebSocket (`/api/v1/ws`):** Real-time bidirectional channel broadcasting `BRAIN_STARTED`, `BRAIN_COMPLETED`, `VOICE_STATE_CHANGED`, `HEALTH_CHANGED`, and `ERROR_OCCURRED`. Includes automatic secret redaction (`SecretRedactionFilter`).

---

## 6. Brain & Agent Architecture

The cognitive engine resides in `src/brain/`:
- **`AstraAgent` (`src/brain/agent.py`):** Central orchestrator. Manages tool execution iterations (up to `agent_max_iterations=5`), loop detection, simple command fast-paths, context memory updates, and structured decision routing.
- **LLM Pipeline (`src/brain/llm/`):**
  - `LLMClient`: Handles timeouts (`10.0s`), bounded retries, and quota exhaustion short-circuiting (`RESOURCE_EXHAUSTED` / 429).
  - `GeminiProvider`: Connects to `google-genai` SDK with `gemini-3.6-flash`. Compiles dictionary schemas to Gemini `types.Tool` protobuf specifications with in-memory caching.
  - `MockLLMProvider`: Deterministic mock for unit testing and offline development.
  - `LLMProviderFactory`: Factory resolving configured providers explicitly.
- **Context Management (`src/brain/context/manager.py`):** Maintains conversational turns, formats context prompts for LLM queries, and deduplicates in-flight messages.
- **Deterministic Fallback Engine (`src/brain/intent.py`):** Rule-based regex intent matcher invoked if LLM is unavailable or quota is exceeded.

---

## 7. Voice Architecture

Located in `src/voice/`:
- **Microphone Management (`src/voice/microphone.py`):** Hardware device enumeration, device caching, and single-owner audio recording via `sounddevice`.
- **Voice Activity Detection (`src/voice/vad.py`):** Audio RMS calculation and energy threshold gating (>100.0) to filter background silence.
- **Speech-To-Text (`src/voice/stt.py`):** `SpeechRecognitionSTTProvider` utilizing Google Web Speech API; `MockSTTProvider` for unit tests.
- **Text-To-Speech (`src/voice/tts.py`):** Windows native SAPI5 via `pyttsx3` with engine caching under thread lock; `MockTTSProvider` for unit tests.
- **Hands-Free Wake Word (`src/voice/wake/`):** Continuous local background listener detecting "Hey ASTRA" with acoustic energy gating, command extraction, compound phrase splitting ("Hey Astra, open Chrome"), command timeout protection, and TTS self-trigger suppression.

---

## 8. Tool Architecture

Tools are centralized in `src/tools/` under `ToolRegistry`:
- **Base Interface (`src/tools/base.py`):** Abstract `BaseTool` requiring `name`, `description`, `permission_level`, `parameters_schema`, `validate()`, and `execute()`.
- **Domain Categories:**
  - `src/tools/filesystem/`: OpenFolder, OpenFile, SearchFiles, CreateFolder, CreateTextFile, RenameFile, MoveFile, CopyFile, DeleteFile, OrganizeFolder, FileMetadata.
  - `src/tools/applications/`: OpenApplication, CloseApplication, ApplicationStatus, OpenProject.
  - `src/tools/system/`: SystemInformation, ResourceInformation, VolumeControl, Screenshot.
  - `src/tools/web/`: SearchWeb, FetchWebpage, ResearchTopic.
  - `src/tools/memory/`: Remember, RetrieveMemory, ListMemories, ForgetMemory.
  - `src/tools/vision/`: AnalyzeActiveWindow.

---

## 9. Security Architecture

Located in `src/security/`:
- **Permission Model (`src/security/permissions.py`):** Three permission tiers (`SAFE`, `CONFIRM_REQUIRED`, `ADMIN`). Gated by `permissions_mode` (`STRICT`, `NORMAL`, `PERMISSIVE`).
- **Secret Redaction (`src/security/auditor.py`):** `SecretRedactionFilter` scrubs API keys, auth tokens, passwords, and user secrets from all logs and WebSocket broadcasts.
- **Prompt Injection Defense (`src/security/injection.py`):** Sanitizes inputs against adversarial delimiter hijacking and system prompt override attempts.
- **Execution Verification (`src/execution/verifier.py`):** Verifies OS file creation, process launching, or window state changes before confirming tool success.

---

## 10. Memory Architecture

Located in `src/memory/`:
- **SQLite Database (`src/memory/db.py`):** Persistent storage using SQLite at `data/astra_memory.db`.
- **Repository (`src/memory/repository.py`):** CRUD operations for `MemoryRecord`, categorizing facts, user preferences, interaction logs, and contextual notes.
- **Memory Manager (`src/memory/manager.py`):** Handles semantic retrieval, expiration policies (`memory_expiration_days=30`), and memory formatting for agent prompt injection.

---

## 11. Vision Architecture

Located in `src/vision/`:
- **Capture (`src/vision/capture/`):** Full-desktop and active-window screenshot capture via `mss` / Pillow.
- **OCR (`src/vision/ocr/`):** `OCRProvider` abstraction with `MockOCRProvider` default.
- **Visual Context (`src/vision/context/`):** Aggregates active window title, process executable, OCR text, and visual bounding boxes into structured `VisionContext`.

---

## 12. Web Architecture

Located in `src/web/`:
- **Search (`src/web/search/`):** `DuckDuckGoSearchProvider` for free web searching; `MockSearchProvider` for testing.
- **Retrieval (`src/web/retrieval/`):** `WebFetcher` with size-capped downloads (`MAX_FETCH_SIZE_MB=1.0`) and `WebContentParser` HTML-to-text extraction.
- **Research Synthesizer (`src/web/research/`):** Source ranker with domain deduplication and citation formatting.

---

## 13. Task & Automation Architecture

Located in `src/task/` and `src/automation/`:
- **Task Engine (`src/task/`):** Goal decomposition into directed dependency graphs (`TaskGraph`), sequential execution (`TaskExecutor`), and status tracking (`PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`).
- **Automation Scheduler (`src/automation/`):** Cron and interval scheduler for recurring background tasks, quiet hours enforcement (`23:00` - `07:00`), and daily notification caps.

---

## 14. Database Architecture

- **Engine:** SQLite 3 via standard library `sqlite3`.
- **Storage Location:** `data/astra_memory.db`.
- **Tables:**
  - `memories`: Long-term personal assistant context.
  - `tasks`, `task_steps`: Autonomous goal tracking.
  - `automations`: Proactive recurring schedules.
- **Concurrency & WAL:** Operates under standard connection isolation with thread-safe access.

---

## 15. Test Architecture

Located in `tests/`:
- 48 test modules covering 119 test cases.
- Uses `pytest` with extensive mocking for hardware (`MockMicrophone`, `MockSTTProvider`, `MockTTSProvider`), external APIs (`MockLLMProvider`, `MockSearchProvider`), and OS processes.
- Execution time: ~80 seconds (due to real-time audio thread sleeps in wake-word test suite).
- Baseline pass rate: **119 / 119 passed (100%)**.

---

## 16. Duplicate Systems

1. **Application Launchers:**
   - Root `main.py` (Production FastAPI + WebSocket + React WebEngine launcher).
   - `src/main.py` (Legacy direct PySide6 launcher).
2. **Intent Recognition:**
   - `src/brain/agent.py` uses LLM-first reasoning with tool schemas.
   - `src/brain/intent.py` maintains standalone `RuleBasedIntentRecognizer` for deterministic fallback.
3. **Frontend Lockfiles:**
   - Root `package-lock.json` (spurious empty package file).
   - `Astra voice UI/package-lock.json` (actual React/Vite dependency lockfile).

---

## 17. Legacy Systems

1. **`src/main.py`:** Legacy entrypoint that bypasses the modern API and WebEngine stack.
2. **Native PySide6 Desktop Widgets (`src/ui/main_window.py`, `src/ui/components/`, `src/ui/pages/`):** Built prior to Phase 18's Google Stitch React UI migration.
3. **`src/brain/router.py`:** Earlier regex routing mechanism largely superseded by `AstraAgent`'s controlled LLM orchestration loop.

---

## 18. Mock Systems

The codebase contains mocks across 6 subsystems:
- **LLM:** `MockLLMProvider` in `src/brain/llm/mock_provider.py`.
- **STT:** `MockSTTProvider` in `src/voice/stt.py`.
- **TTS:** `MockTTSProvider` in `src/voice/tts.py`.
- **Search:** `MockSearchProvider` in `src/web/search/mock_provider.py`.
- **OCR:** `MockOCRProvider` in `src/vision/ocr/mock_provider.py`.
- **Vision:** `MockVisionProvider` in `src/vision/providers/mock_provider.py`.

---

## 19. Dead / Unused Code Candidates

- **Root `package-lock.json`:** Empty lockfile `{ "packages": {} }` from root `npm` execution.
- **`src/brain/router.py`:** Simple intent router class no longer in the primary agent command pipeline.
- **Tracked SQLite Database (`data/astra_memory.db`):** Tracked in git index despite `.gitignore` entry, causing continuous dirty diffs on test runs.

---

## 20. Technical Debt

1. **Silent Fallback in Provider Factories:**
   - `src/web/search/factory.py`: Returns `MockSearchProvider()` if any unrecognized provider string is passed.
   - `src/vision/ocr/factory.py` & `src/vision/providers/factory.py`: Return mock providers regardless of input string without warning.
2. **Dynamic Port Coordination:**
   - Backend dynamically binds ports 8000–8020 if 8000 is occupied. While React WebEngine handles this via `window.location.host`, standalone Vite dev server (`localhost:5173`) assumes 8000. Documented for V2-03.
3. **Database In-Repo Tracking:**
   - `data/astra_memory.db` is tracked in git index, creating commit clutter when tests execute locally.

---

## 21. Architecture Risks

1. **External API Quota Exhaustion:**
   - Real Gemini API (`gemini-3.6-flash`) has rate limits. Bounded retries and fast-path fallback protect the user experience, but multi-turn operations can consume daily quota rapidly.
2. **Audio Hardware Locking:**
   - Exclusive mode microphone access on some Windows drivers can cause issues if shared across multiple process instances.
3. **PySide6 / WebEngine Binary Footprint:**
   - Packaging PySide6 QtWebEngine adds significant disk weight, requiring clean distribution configuration in later phases.

---

## 22. Recommended Canonical Architecture

The canonical ASTRA V2 architecture establishes a clean, layered structure:

```text
┌────────────────────────────────────────────────────────┐
│                      INTERFACES                        │
│  React Stitch UI (WebEngine) │ Terminal CLI │ REST/WS  │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                    APPLICATION CORE                    │
│     SystemLifecycle │ Config │ Logger │ HealthManager  │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                   AGENT / COGNITION                    │
│    AstraAgent │ LLMClient │ ContextManager │ Planner   │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                     CAPABILITIES                       │
│    Tools │ Voice │ Vision │ Memory │ Web │ Automation  │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                    INFRASTRUCTURE                      │
│     Permissions │ Security Auditor │ SQLite Database   │
└────────────────────────────────────────────────────────┘
```
