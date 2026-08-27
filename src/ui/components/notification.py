"""
Stitch Notification Toast Component.
Aligns with Google Stitch glassmorphic floating notifications with ambient color accents.
"""

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget


class NotificationToast(QFrame):
    """Temporary floating glassmorphic notification banner."""

    def __init__(self, level: str, message: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 12)

        icon_str = "✓" if level == "SUCCESS" else ("⚠" if level == "WARNING" else "✕")
        color = "#34d399" if level == "SUCCESS" else ("#fbbf24" if level == "WARNING" else "#ffb4ab")

        lbl = QLabel(f"{icon_str}  {message}")
        lbl.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {color};")
        layout.addWidget(lbl)

        self.setStyleSheet(f"""
            QFrame {{
                background-color: #1e2021;
                border: 1px solid {color};
                border-radius: 16px;
            }}
        """)

        # Auto-dismiss after 4 seconds
        QTimer.singleShot(4000, self.close)
