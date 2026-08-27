"""
Stitch Command Input Bar Component.
Aligns with Google Stitch pill-shaped input container with glowing microphone button and submit action.
"""

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget


class CommandInputBar(QWidget):
    """Pill-shaped glassmorphic command input bar."""

    sig_submit = Signal(str)
    sig_mic_toggle = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Text input line (Pill rounded)
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ask ASTRA or type a command (e.g. 'open calculator', 'summarize project')...")
        self.input_field.returnPressed.connect(self._on_submit)

        # Microphone Toggle Button (Stitch Living Light Violet)
        self.mic_btn = QPushButton("🎙")
        self.mic_btn.setObjectName("IconButton")
        self.mic_btn.setToolTip("Activate Voice Listening")
        self.mic_btn.setFixedWidth(50)
        self.mic_btn.setFixedHeight(50)
        self.mic_btn.setStyleSheet("""
            QPushButton#IconButton {
                background-color: #7c5cfc;
                color: #FFFFFF;
                border: none;
                border-radius: 25px;
                font-size: 20px;
            }
            QPushButton#IconButton:hover {
                background-color: #947dff;
            }
        """)
        self.mic_btn.clicked.connect(self.sig_mic_toggle.emit)

        # Submit Button (Stitch Pill)
        self.submit_btn = QPushButton("Send")
        self.submit_btn.setFixedWidth(90)
        self.submit_btn.setFixedHeight(50)
        self.submit_btn.clicked.connect(self._on_submit)

        layout.addWidget(self.input_field, stretch=1)
        layout.addWidget(self.mic_btn)
        layout.addWidget(self.submit_btn)

    def _on_submit(self) -> None:
        text = self.input_field.text().strip()
        if text:
            self.sig_submit.emit(text)
            self.input_field.clear()
