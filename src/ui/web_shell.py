"""
PySide6 WebEngine Desktop Shell Host (Stitch React UI Integration).
Launches the native desktop window host presenting the React Stitch UI connected to Python ASTRA Engine.
"""

import sys
from PySide6.QtCore import QUrl, Qt
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout
from src.core.logger import get_logger

logger = get_logger()


class AstraWebWindow(QMainWindow):
    """Desktop Window Host presenting the React Stitch UI via QWebEngineView."""

    def __init__(self, server_url: str = "http://127.0.0.1:8000", parent: QWidget | None = None):
        super().__init__(parent)
        self.server_url = server_url

        self.setWindowTitle("ASTRA — Desktop Personal AI Assistant")
        self.resize(1280, 850)
        self.setMinimumSize(960, 640)

        # Central Widget & WebEngineView
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.web_view = QWebEngineView()
        self.web_view.setUrl(QUrl(self.server_url))
        layout.addWidget(self.web_view)

        logger.info(f"AstraWebWindow initialized loading URL: {self.server_url}")

    def closeEvent(self, event):
        """Handle window close event gracefully."""
        logger.info("AstraWebWindow close requested.")
        super().closeEvent(event)
