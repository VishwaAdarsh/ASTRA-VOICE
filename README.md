# ASTRA — Personal AI Assistant for Windows

![ASTRA Assistant](https://img.shields.io/badge/ASTRA-Phase_7_Memory_Subsystem-blue.svg)
![Python Version](https://img.shields.io/badge/python-3.10%2B-green.svg)
![Platform](https://img.shields.io/badge/platform-Windows-0078D6.svg)

**ASTRA** is a long-term personal AI computer assistant for Windows designed to understand natural language, communicate through voice and text, control authorized computer operations, search the web, manage persistent long-term memory, and assist with daily productivity.

> **Current Phase:** Phase 7 Memory, Personal Context & Long-Term Intelligence (Completed).  
> Phase 7 introduces local SQLite persistent memory storage (`data/astra_memory.db`), candidate memory extraction, secret filtering (API keys, passwords), preference conflict resolution, query-driven memory retrieval, native PySide6 Desktop GUI Memory Dashboard, and Voice memory commands.







---

## 1. Overview

The core objective of Phase 1 is to establish a strict, layered execution pipeline where user commands are parsed, matched to deterministic intents, routed to registered safe tools, verified, and executed under permission policy controls without arbitrary OS command execution.

```text
User Command
    ↓
Command Processing
    ↓
Intent Recognition
    ↓
Tool Selection
    ↓
Permission Check
    ↓
Tool Execution
    ↓
Result Verification
    ↓
Response Formatting
    ↓
Logging
```

---

## 2. Architecture

ASTRA decouples reasoning/intent processing from system execution. The system consists of six distinct layers:

1. **Core Infrastructure (`src/core/`)**: Configuration loading, centralized file logging (`data/logs/astra.log`), exception definitions, and lifecycle startup/shutdown management.
2. **Brain & Intent Engine (`src/brain/`)**: Domain models (`Command`, `Intent`, `ToolRequest`, `ToolResult`), abstract `IntentRecognizer` interface (implemented by `RuleBasedIntentRecognizer`), and `IntentRouter`.
3. **Tool System (`src/tools/`)**: Abstract `BaseTool` class, central `ToolRegistry` enforcement, and allowlisted Phase 1 tools.
4. **Security & Permissions (`src/security/`)**: `PermissionManager` evaluating `SAFE`, `CONFIRM`, and `RESTRICTED` policies, plus user confirmation handlers.
5. **Execution & Verification (`src/execution/`)**: `ToolExecutor` and `ToolVerifier` providing pre/post execution checks and exception isolation.
6. **User Interface (`src/interfaces/`)**: Interactive terminal CLI interface.

---

## 3. Current Capabilities (Phase 1)

ASTRA Phase 1 supports four allowlisted tool categories:

| Tool Name | Example Commands | Actions / Behavior |
| :--- | :--- | :--- |
| **Open Application** | `open calculator`, `open notepad`, `open chrome`, `open vscode` | Launches allowlisted Windows desktop applications safely using controlled executable mappings. |
| **Open Folder** | `open downloads`, `open documents`, `open desktop`, `open pictures` | Opens authorized system folders in Windows File Explorer after path existence verification. |
| **Open Website** | `open youtube`, `open google`, `open github`, `open https://...` | Opens verified URLs and site shortcuts in the user's default web browser. |
| **System Information**| `show system information`, `system info`, `specs` | Gathers non-sensitive OS specs, Python runtime version, hostname, and RAM availability using `psutil`. |

---

## 4. Project Structure

```text
ASTRA/
├── README.md                  # Comprehensive project documentation
├── architecture.md            # System architectural blueprint
├── requirements.txt           # Dependency manifest
├── .env.example               # Environment variables template
├── .gitignore                 # Git ignore rules
│
├── src/
│   ├── __init__.py
│   ├── main.py                # Main application entry point
│   │
│   ├── core/                  # Configuration, logging, lifecycle & exceptions
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── lifecycle.py
│   │   ├── exceptions.py
│   │   └── logger.py
│   │
│   ├── brain/                 # Models, Intent Recognition, Routing & Orchestration
│   │   ├── __init__.py
│   │   ├── agent.py
│   │   ├── intent.py
│   │   ├── router.py
│   │   └── models.py
│   │
│   ├── tools/                 # Base Tool class, Registry & Allowlisted Tools
│   │   ├── __init__.py
│   │   ├── registry.py
│   │   ├── base.py
│   │   ├── applications.py
│   │   ├── filesystem.py
│   │   ├── browser.py
│   │   └── system.py
│   │
│   ├── security/              # Security permissions & confirmation prompts
│   │   ├── __init__.py
│   │   ├── permissions.py
│   │   └── confirmation.py
│   │
│   ├── execution/             # Tool executor & pre/post verifiers
│   │   ├── __init__.py
│   │   ├── executor.py
│   │   └── verifier.py
│   │
│   └── interfaces/            # User interface (Terminal CLI)
│       ├── __init__.py
│       └── cli.py
│
├── tests/                     # Automated Pytest suite
│   ├── __init__.py
│   ├── test_intent.py
│   ├── test_router.py
│   ├── test_tools.py
│   ├── test_permissions.py
│   └── test_executor.py
│
└── data/
    └── logs/                  # Development & runtime log storage
        └── .gitkeep
```

---

## 5. Installation

### Prerequisites
- Operating System: Windows 10 or Windows 11
- Python: Version 3.10 or higher

### Setup Steps
1. Clone or navigate to the repository directory:
   ```cmd
   cd ASTRA-VOICE
   ```
2. Create and activate a Python virtual environment (optional but recommended):
   ```cmd
   python -m venv .venv
   .venv\Scripts\activate
   ```
3. Install dependencies:
   ```cmd
   pip install -r requirements.txt
   ```

---

## 6. Environment Configuration

Copy `.env.example` to `.env` to configure custom environment settings:

```cmd
copy .env.example .env
```

Available options inside `.env`:
```env
ASTRA_ENV=development
LOG_LEVEL=INFO
LOG_FILE_PATH=data/logs/astra.log
PERMISSIONS_MODE=NORMAL
```

---

## 7. Running ASTRA

To start the interactive ASTRA CLI:

```cmd
python src/main.py
```

### Example Interactive Session:
```text
========================================
              ASTRA
      Personal AI Assistant (Phase 1)
========================================

You > open calculator
ASTRA > ✓ Calculator opened.

You > open downloads
ASTRA > ✓ Downloads opened.

You > open youtube
ASTRA > ✓ Youtube opened.

You > show system information
ASTRA > ✓ Operating System: Windows 10 (AMD64)
Python Version: 3.14.6
Hostname: DESKTOP-MAIN
RAM: 14.2 GB free of 31.8 GB total

You > do something unsupported
ASTRA > I don't understand that command yet.
```

---

## 8. Testing

Run the automated test suite with `pytest`:

```cmd
python -m pytest
```

All OS-level calls (application launches, folder openings, browser navigation) are mocked during testing to ensure tests run fast and deterministically across environments.

---

## 9. Development Roadmap

- [x] **Phase 1: Foundation & Core Engine (Current)**
  - Modular architecture setup
  - Domain data models & explicit status enums
  - Allowlisted tool registry (`open_application`, `open_folder`, `open_website`, `system_information`)
  - Isolated Rule-Based Intent Recognizer behind abstract interface
  - Security permission framework & verification layer
  - Centralized logging & interactive CLI
  - Comprehensive unit test suite
- [ ] **Phase 2: Local & Cloud LLM Integration**
  - Replace/augment `RuleBasedIntentRecognizer` with `LLMIntentRecognizer`
  - Structured function calling & dynamic parameter extraction
- [ ] **Phase 3: Voice & Audio Pipeline**
  - Wake word detection
  - Offline Speech-To-Text (Whisper / Vosk) & Text-To-Speech (Piper / Edge-TTS)
- [ ] **Phase 4: Advanced Computer Control & Web Research**
  - Authorized OS automation, file searching, browser automation
- [ ] **Phase 5: Persistent Memory & Context Engine**
  - Local vector database & long-term conversation history

---

## 10. Security Principles

1. **No Arbitrary Shell Execution**: ASTRA explicitly forbids generic shell commands like `run_any_command()`.
2. **Allowlisted Tools Only**: Every executable capability must be defined as a `BaseTool` subclass and registered in `ToolRegistry`.
3. **Decoupled Brain and OS Execution**: Intent processing never communicates directly with the OS; all calls pass through `ToolExecutor` and `PermissionManager`.
4. **No Hardcoded Secrets**: Configuration is managed strictly via environment variables (`.env`).
5. **Zero Secret Logging**: Secrets, credentials, and API keys are filtered out of log outputs (`data/logs/astra.log`).
