# ADR-004: Project Structure & Architectural Layering

**Status:** Accepted  
**Date:** 2026-09-16  
**Phase:** V2-01  

---

## Context
As ASTRA expanded to include 15 distinct subsystems, clear boundaries and dependency direction became essential to avoid circular imports, hidden coupling, and inversion of control. Previous iterations saw UI components occasionally importing tools directly, or tools depending on presentation layers.

---

## Decision
Establish a strict five-tier architectural hierarchy governing all ASTRA V2 code:

1. **Core Layer (`src/core/`):**
   - Configuration (`Config`), Lifecycle (`SystemLifecycle`), Logging, Health, Recovery, Versioning.
   - Lowest level; depends on nothing inside the project.
2. **Infrastructure & Security Layer (`src/security/`, `src/database/`, `src/execution/`):**
   - Permission management, secret redaction, SQLite database connectivity, subprocess execution, result verification.
   - Depends only on Core.
3. **Capabilities Layer (`src/tools/`, `src/voice/`, `src/vision/`, `src/memory/`, `src/web/`, `src/task/`, `src/automation/`):**
   - Domain-specific tools, audio devices, vision captures, memory repositories, web scrapers, and schedulers.
   - Depends on Infrastructure and Core.
4. **Agent / Cognition Layer (`src/brain/`):**
   - `AstraAgent`, `LLMClient`, `GeminiProvider`, Context Manager, Prompt Templates, Intent Fallbacks.
   - Coordinates Capability and Infrastructure components; depends on Core, Infrastructure, and Capabilities.
5. **Interfaces Layer (`src/api/`, `src/interfaces/`, `Astra voice UI/`):**
   - FastAPI server, WebSockets, CLI, PySide6 WebEngine Shell, React frontend.
   - The presentation boundary; drives the Agent and Core subsystems.

**Rule:** Dependencies must flow downward ($\text{Interfaces} \rightarrow \text{Agent} \rightarrow \text{Capabilities} \rightarrow \text{Infrastructure} \rightarrow \text{Core}$). Lower layers must never import or depend upon higher layers.

---

## Consequences
- **Positive:**
  - Prevents circular imports and dependency tangles.
  - Subsystems can be tested in isolation with high reliability.
  - Clean modularity allows swapping interfaces or capabilities without rewriting core engine logic.
- **Negative:**
  - Requires disciplined module design; data passing between layers must use explicit DTOs.
