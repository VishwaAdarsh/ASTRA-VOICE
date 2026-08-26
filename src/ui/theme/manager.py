"""
Centralized Theme Manager for ASTRA UI.
"""

from typing import Literal
from PySide6.QtWidgets import QApplication
from src.ui.theme.stylesheet import generate_stylesheet
from src.ui.theme.tokens import DARK_PALETTE, LIGHT_PALETTE, ColorPalette

ThemeMode = Literal["dark", "light", "system"]


class ThemeManager:
    """Singleton managing application dark/light themes and QSS updates."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ThemeManager, cls).__new__(cls)
            cls._instance.current_theme: ThemeMode = "dark"
            cls._instance.palette: ColorPalette = DARK_PALETTE
        return cls._instance

    def set_theme(self, theme_name: ThemeMode, app: QApplication | None = None) -> None:
        """Switch active UI theme and update QApplication stylesheet."""
        self.current_theme = theme_name
        if theme_name == "light":
            self.palette = LIGHT_PALETTE
        else:
            self.palette = DARK_PALETTE  # Dark is default

        if app is None:
            app = QApplication.instance()

        if app:
            stylesheet = generate_stylesheet(self.palette)
            app.setStyleSheet(stylesheet)
