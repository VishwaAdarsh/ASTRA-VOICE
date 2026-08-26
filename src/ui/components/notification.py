"""
Toast / Banner Notification Component.
"""

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget


class NotificationToast(QFrame):
    """Temporary notification banner."""

    def __init__(self, level: str, message: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)

        icon_str = "✓" if level == "SUCCESS" else ("⚠" if level == "WARNING" else "✕")
        color = "#10B981" if level == "SUCCESS" else ("#F59E0B" if level == "WARNING" else "#F43F5E")

        lbl = QLabel(f"{icon_str}  {message}")
        lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {color};")
        layout.addWidget(lbl)

        self.setStyleSheet(f"""
            QFrame {{
                background-color: #1E293B;
                border: 1px solid {color};
                border-radius: 8px;
            }}
        """)

        # Auto-dismiss after 4 seconds
        QTimer.singleShot(4000, self.close)
