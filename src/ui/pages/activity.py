"""
Activity Log Page Component.
Displays chronological execution history and diagnostic details.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget
from src.ui.controllers.app_controller import AppController


class ActivityPage(QWidget):
    """Activity Log View."""

    def __init__(self, controller: AppController, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Activity History")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #F8FAFC;")
        subtitle = QLabel("Traceable audit log of command receipts, tool selections, and execution results.")
        subtitle.setStyleSheet("font-size: 13px; color: #94A3B8;")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Activity List Widget
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #1E293B;
                border: 1px solid #334155;
                border-radius: 10px;
                padding: 10px;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #334155;
                border-radius: 6px;
            }
            QListWidget::item:hover {
                background-color: #334155;
            }
        """)

        layout.addWidget(self.list_widget)

        # Connect controller activity signal
        self.controller.sig_activity_logged.connect(self._on_activity_logged)

        # Initial populate from history
        for entry in self.controller.activity_history:
            self._on_activity_logged(entry)

    def _on_activity_logged(self, entry: dict) -> None:
        if entry.get("type") == "COMMAND":
            text = f"Command: '{entry.get('command')}' [Status: {entry.get('status')}]"
        else:
            text = f"Response: '{entry.get('response')}' [Result: {entry.get('status')}]"

        item = QListWidgetItem(text)
        self.list_widget.addItem(item)
