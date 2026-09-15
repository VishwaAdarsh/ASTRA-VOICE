# ADR-001: Canonical Application Entry Point

**Status:** Accepted  
**Date:** 2026-09-16  
**Phase:** V2-01  

---

## Context
ASTRA had two separate executable entry points:
1. `main.py` at repository root, which launches the full production runtime (system lifecycle, port finder, background FastAPI REST/WebSocket server, hands-free wake word listener, and PySide6 WebEngine desktop window).
2. `src/main.py`, which originally launched an older native PySide6 desktop GUI (`src/ui/app.py`) without the API server or the React Stitch UI.

Having multiple ambiguous entry points created confusion regarding how the application should be booted, tested, and packaged.

---

## Decision
1. **Root `main.py` is established as the single canonical production entry point** for all ASTRA operational modes (Desktop GUI, Terminal CLI via `--cli`, Backend Server via `--backend`).
2. **`src/main.py` is marked as a legacy compatibility entry point.** It emits a notice directing users to root `main.py` and delegates execution while maintaining backward compatibility for legacy invocations.
3. Documentation and development scripts will exclusively reference root `main.py`.

---

## Consequences
- **Positive:**
  - One single source of truth for application startup.
  - Guarantees that the FastAPI backend, WebSocket bus, wake-word listener, and React Stitch UI are consistently initialized together.
  - Prevents dual-runtime desynchronization.
- **Negative:**
  - Developers familiar with running `python src/main.py` must adjust to `python main.py`.
