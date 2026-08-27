"""
Stitch Conversation Message Bubble Widgets.
Aligns with Google Stitch "Conversation Thread" design cards with glassmorphism styling.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class MessageBubble(QFrame):
    """Stitch glassmorphic conversation message container."""

    def __init__(self, sender: str, text: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.sender = sender.upper()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        # Sender Label
        sender_lbl = QLabel(self.sender)
        sender_color = "#7c5cfc" if self.sender == "ASTRA" else "#cebdff"
        sender_lbl.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {sender_color}; letter-spacing: 0.5px;")

        # Content Text
        content_lbl = QLabel(text)
        content_lbl.setWordWrap(True)
        content_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        content_lbl.setStyleSheet("font-size: 14px; color: #e2e2e3; line-height: 1.5;")

        layout.addWidget(sender_lbl)
        layout.addWidget(content_lbl)

        # Container styling based on sender (Stitch Glass Cards)
        if self.sender == "ASTRA":
            self.setStyleSheet("""
                QFrame {
                    background-color: #1e2021;
                    border: 1px solid #484555;
                    border-radius: 16px;
                    margin-right: 60px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #1a1c1d;
                    border: 1px solid #7c5cfc;
                    border-radius: 16px;
                    margin-left: 60px;
                }
            """)
