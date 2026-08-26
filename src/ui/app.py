"""
PySide6 Application Launcher and Lifecycle Integration.
"""

import sys
from PySide6.QtWidgets import QApplication
from src.core.lifecycle import SystemLifecycle
from src.ui.controllers.app_controller import AppController
from src.ui.main_window import MainWindow
from src.ui.theme.manager import ThemeManager
from src.voice.manager import VoiceManager


def launch_ui() -> None:
    """Launch the ASTRA PySide6 Desktop GUI."""
    app = QApplication(sys.argv)
    app.setApplicationName("ASTRA Personal AI Assistant")

    # Initialize Core & Voice Engine
    lifecycle = SystemLifecycle()
    agent = lifecycle.startup()
    voice_manager = VoiceManager(agent=agent, config=lifecycle.config)

    # Initialize Controller Bridge
    controller = AppController(agent=agent, voice_manager=voice_manager)

    # Apply Theme
    theme_manager = ThemeManager()
    theme_manager.set_theme("dark", app=app)

    # Create & Show Main Window
    window = MainWindow(controller=controller)
    window.show()

    # Run main Qt event loop
    try:
        sys.exit(app.exec())
    finally:
        lifecycle.shutdown()


if __name__ == "__main__":
    launch_ui()
