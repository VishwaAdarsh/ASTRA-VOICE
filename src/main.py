"""
ASTRA Main Entry Point.
Launches the PySide6 Desktop Interface by default, or Terminal CLI / Voice mode via flags.
"""

import os
import sys
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
    """Main application execution point."""
    if "--cli" in sys.argv or "-c" in sys.argv:
        run_cli(start_in_voice_mode=False)
    elif "--voice" in sys.argv or "-v" in sys.argv:
        run_cli(start_in_voice_mode=True)
    else:
        # Default: Launch PySide6 Desktop GUI Interface
        launch_ui()


if __name__ == "__main__":
    main()
