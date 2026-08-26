"""
Footer Status Bar Component.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget


class StatusBar(QFrame):
    """Footer status bar."""

    def __init__(self, tool_count: int = 4, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("StatusBar")
        self.setFixedHeight(30)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)

        self.status_lbl = QLabel("● ASTRA Online")
        self.status_lbl.setStyleSheet("color: #10B981; font-weight: 600;")

        self.mic_lbl = QLabel("🎙 Microphone Ready")
        self.tools_lbl = QLabel(f"⚙ {tool_count} Approved Tools")

        layout.addWidget(self.status_lbl)
        layout.addStretch()
        layout.addWidget(self.mic_lbl)
        layout.addSpacing(20)
        layout.addWidget(self.tools_lbl)

    def set_voice_state(self, state: str) -> None:
        """Update voice status text in status bar."""
        self.mic_lbl.setText(f"🎙 Voice: {state}")
