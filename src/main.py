"""
ASTRA Legacy Compatibility Entry Point.
[LEGACY / COMPATIBILITY ONLY]

The canonical production entry point for ASTRA V2 is root `main.py`:
    python main.py

This file (`src/main.py`) is retained for backward compatibility with earlier
scripts and development tooling that launched the older native PySide6 UI.
"""

import os
import sys
import warnings
from pathlib import Path

# Force UTF-8 encoding for standard output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to sys.path if not present
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.interfaces.cli import run_cli
from src.ui.app import launch_ui


def main():
    """Legacy application execution point."""
    print("[ASTRA] Notice: 'src/main.py' is a legacy entry point. For the full production")
    print("[ASTRA] system (FastAPI + WebSocket + React WebEngine UI), run 'python main.py'.\n")

    if "--cli" in sys.argv or "-c" in sys.argv:
        run_cli(start_in_voice_mode=False)
    elif "--voice" in sys.argv or "-v" in sys.argv:
        run_cli(start_in_voice_mode=True)
    else:
        # Launch legacy native PySide6 Desktop GUI Interface
        launch_ui()


if __name__ == "__main__":
    main()

