"""
ASTRA — Personal AI Assistant for Windows
Single Primary Application Entry Point (Phase 12 Final Integration).

Usage:
  python main.py             # Launch PySide6 Desktop GUI
  python main.py --cli       # Launch Terminal Interactive CLI
  python main.py --version   # Display Version Information
  python main.py --debug     # Launch in Debug Mode
"""

import argparse
import signal
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.core.config import Config
from src.core.lifecycle import SystemLifecycle
from src.core.version import __version__, APP_FULL_NAME


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description=APP_FULL_NAME)
    parser.add_argument("--cli", action="store_true", help="Launch in interactive terminal CLI mode")
    parser.add_argument("--version", action="store_true", help="Display application version and exit")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")
    return parser.parse_args()


def main():
    """Main Application Entry Point."""
    args = parse_args()

    if args.version:
        print(f"{APP_FULL_NAME} v{__version__}")
        sys.exit(0)

    config = Config()
    if args.debug:
        config.log_level = "DEBUG"

    lifecycle = SystemLifecycle(config=config)
    agent = lifecycle.startup()

    # Register OS signal handlers for graceful shutdown
    def _sig_handler(sig, frame):
        print("\nShutdown signal received. Exiting ASTRA...")
        lifecycle.shutdown(agent)
        sys.exit(0)

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    if args.cli:
        from src.interfaces.cli import InteractiveCLI
        cli = InteractiveCLI(agent=agent)
        try:
            cli.start()
        finally:
            lifecycle.shutdown(agent)
    else:
        try:
            from PySide6.QtWidgets import QApplication
            from src.ui.controllers.app_controller import AppController
            from src.ui.main_window import MainWindow
            from src.ui.theme.manager import ThemeManager
            from src.voice.manager import VoiceManager

            app = QApplication.instance() or QApplication(sys.argv)
            theme_mgr = ThemeManager()
            theme_mgr.apply_theme(app, "dark")

            voice_mgr = VoiceManager(agent=agent)
            controller = AppController(agent=agent, voice_manager=voice_mgr)

            window = MainWindow(controller=controller)
            window.show()

            sys.exit(app.exec())
        except Exception as e:
            print(f"Warning: Could not launch GUI ({e}). Falling back to interactive CLI interface...")
            from src.interfaces.cli import InteractiveCLI
            cli = InteractiveCLI(agent=agent)
            try:
                cli.start()
            finally:
                lifecycle.shutdown(agent)


if __name__ == "__main__":
    main()
