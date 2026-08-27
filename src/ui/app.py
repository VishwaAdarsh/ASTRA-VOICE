"""
PySide6 Application Launcher (Stitch Design System Integration).
Single primary UI launcher for ASTRA Desktop UI.
"""

import sys
from PySide6.QtWidgets import QApplication
from src.core.lifecycle import SystemLifecycle
from src.ui.controllers.app_controller import AppController
from src.ui.main_window import MainWindow
from src.ui.theme.manager import ThemeManager
from src.voice.manager import VoiceManager


def launch_ui() -> None:
    """Launch the ASTRA PySide6 Desktop GUI with Stitch Design System."""
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("ASTRA Personal AI Assistant")

    # Initialize Core & Voice Engine
    lifecycle = SystemLifecycle()
    agent = lifecycle.startup()
    voice_manager = VoiceManager(agent=agent, config=lifecycle.config)

    # Initialize Controller Bridge
    controller = AppController(agent=agent, voice_manager=voice_manager)

    # Apply Stitch Theme
    theme_manager = ThemeManager()
    theme_manager.apply_theme(app, "dark")

    # Create & Show Main Window
    window = MainWindow(controller=controller)
    window.show()

    # Run main Qt event loop
    try:
        sys.exit(app.exec())
    finally:
        lifecycle.shutdown(agent)


if __name__ == "__main__":
    launch_ui()
