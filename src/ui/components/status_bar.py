"""
Stitch Ambient Footer Status Bar Component.
Aligns with Google Stitch ambient status indicators with primary living violet highlights.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget


class StatusBar(QFrame):
    """Stitch ambient status bar."""

    def __init__(self, tool_count: int = 31, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("StatusBar")
        self.setFixedHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)

        self.status_lbl = QLabel("● ASTRA Ready")
        self.status_lbl.setStyleSheet("color: #34d399; font-weight: 700; font-size: 13px;")

        self.mic_lbl = QLabel("🎙 Voice Subsystem Ready")
        self.mic_lbl.setStyleSheet("color: #c9c4d8; font-size: 13px;")

        self.tools_lbl = QLabel(f"⚙ {tool_count} Registered Tools")
        self.tools_lbl.setStyleSheet("color: #7c5cfc; font-weight: 600; font-size: 13px;")

        layout.addWidget(self.status_lbl)
        layout.addStretch()
        layout.addWidget(self.mic_lbl)
        layout.addSpacing(24)
        layout.addWidget(self.tools_lbl)

    def set_voice_state(self, state: str) -> None:
        """Update voice status text in status bar."""
        self.mic_lbl.setText(f"🎙 Voice State: {state.capitalize()}")
