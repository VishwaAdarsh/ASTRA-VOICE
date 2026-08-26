"""
ASTRA Desktop Interface Package (Phase 3).
Provides PySide6 native desktop GUI window, pages, components, controllers, and theme system.
"""

from src.ui.app import launch_ui
from src.ui.controllers.app_controller import AppController
from src.ui.main_window import MainWindow

__all__ = ["launch_ui", "AppController", "MainWindow"]
