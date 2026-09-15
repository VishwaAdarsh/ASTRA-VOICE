# ADR-002: Canonical UI Architecture

**Status:** Accepted  
**Date:** 2026-09-16  
**Phase:** V2-01  

---

## Context
ASTRA contained two distinct desktop user interfaces:
1. **React Stitch UI (`Astra voice UI/`):** A modern React 19 web application built with Tailwind CSS, Lucide icons, responsive waveforms, task graphs, memory inspect cards, and real-time WebSocket connection to the Python backend.
2. **Native PySide6 UI (`src/ui/`):** An earlier native Qt widget desktop implementation (`MainWindow`, `components/`, `pages/`, `theme/`).

In Phase 18, the Python backend was established as the single source of truth, and the React Stitch UI became the primary visual interface. However, the older native PySide6 UI files remained in `src/ui/`, leading to ambiguity over which UI is canonical.

---

## Decision
1. **The React Stitch UI hosted in a PySide6 QtWebEngineView shell (`AstraWebWindow`) is established as the canonical production UI.**
2. The React UI is compiled with Vite into `Astra voice UI/dist/` and served directly by FastAPI's static mount at `/`, enabling zero-config desktop execution.
3. The native PySide6 UI widgets in `src/ui/` (`MainWindow`, `pages/`, `components/`, `app.py`) are retained as secondary/legacy desktop references and for potential modular native dialog reuse, but are strictly isolated from the production boot path.

---

## Consequences
- **Positive:**
  - Modern, responsive, and animated user interface using the Google Stitch design system.
  - Consistent presentation across desktop window and browser client connections.
  - Python backend remains the authoritative single source of truth.
- **Negative:**
  - Desktop execution requires `PySide6.QtWebEngineWidgets`, which adds binary weight compared to lightweight native widgets.
