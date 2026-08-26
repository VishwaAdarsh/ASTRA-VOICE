"""
Conversation Message Bubble Widgets.
Renders User commands and ASTRA responses cleanly.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class MessageBubble(QFrame):
    """Single conversation message bubble container."""

    def __init__(self, sender: str, text: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.sender = sender.upper()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        # Sender Label
        sender_lbl = QLabel(self.sender)
        sender_color = "#38BDF8" if self.sender == "ASTRA" else "#10B981"
        sender_lbl.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {sender_color};")

        # Content Text
        content_lbl = QLabel(text)
        content_lbl.setWordWrap(True)
        content_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        content_lbl.setStyleSheet("font-size: 13px; color: #F8FAFC; line-height: 1.4;")

        layout.addWidget(sender_lbl)
        layout.addWidget(content_lbl)

        # Container styling based on sender
        if self.sender == "ASTRA":
            self.setStyleSheet("""
                QFrame {
                    background-color: #1E293B;
                    border: 1px solid #334155;
                    border-radius: 10px;
                    margin-right: 40px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #0F172A;
                    border: 1px solid #38BDF8;
                    border-radius: 10px;
                    margin-left: 40px;
                }
            """)
