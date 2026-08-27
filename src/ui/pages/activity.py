"""
Activity Log Page Component (Stitch Design System Integration).
Displays chronological execution history and diagnostic details.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget
from src.ui.controllers.app_controller import AppController


class ActivityPage(QWidget):
    """Activity Log View matching Stitch design system."""

    def __init__(self, controller: AppController, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(20)

        title = QLabel("Activity History")
        title.setStyleSheet("font-size: 24px; font-weight: 700; color: #e2e2e3;")
        subtitle = QLabel("Traceable audit log of command receipts, tool selections, and execution results.")
        subtitle.setStyleSheet("font-size: 14px; color: #938ea1;")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Activity List Widget
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #1a1c1d;
                border: 1px solid #484555;
                border-radius: 16px;
                padding: 12px;
                color: #e2e2e3;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 12px 16px;
                border-bottom: 1px solid #282a2b;
                border-radius: 8px;
            }
            QListWidget::item:hover {
                background-color: #282a2b;
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
