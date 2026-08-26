"""
Command Input Bar Component.
Combines text QLineEdit, submit button, and microphone toggle button.
"""

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget


class CommandInputBar(QWidget):
    """Bottom command input bar."""

    sig_submit = Signal(str)
    sig_mic_toggle = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Text input line
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type a command (e.g. 'open calculator', 'open downloads')...")
        self.input_field.returnPressed.connect(self._on_submit)

        # Microphone Toggle Button
        self.mic_btn = QPushButton("🎙")
        self.mic_btn.setObjectName("IconButton")
        self.mic_btn.setToolTip("Toggle Voice Mode (Press to Speak)")
        self.mic_btn.setFixedWidth(44)
        self.mic_btn.clicked.connect(self.sig_mic_toggle.emit)

        # Submit Button
        self.submit_btn = QPushButton("Send")
        self.submit_btn.setFixedWidth(80)
        self.submit_btn.clicked.connect(self._on_submit)

        layout.addWidget(self.input_field)
        layout.addWidget(self.mic_btn)
        layout.addWidget(self.submit_btn)

    def _on_submit(self) -> None:
        text = self.input_field.text().strip()
        if text:
            self.sig_submit.emit(text)
            self.input_field.clear()
