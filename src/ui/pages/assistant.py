"""
Assistant Conversation Page Component (Stitch Design System Integration).
Aligns with Stitch "Home - Listening" & "Conversation Thread" design screens.
Single point-of-focus voice visualizer, ambient prompt chips, and message bubbles.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget
from src.brain.models import ToolResult
from src.ui.components.command_input import CommandInputBar
from src.ui.components.message_bubble import MessageBubble
from src.ui.components.voice_orb import VoiceOrb
from src.ui.controllers.app_controller import AppController


class AssistantPage(QWidget):
    """Primary Assistant Interaction View (Stitch Home & Conversation)."""

    CHIPS = [
        "What can you do?",
        "Check system status",
        "Search web for latest AI news",
        "Find Python files in Downloads",
    ]

    def __init__(self, controller: AppController, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 1. Top Voice Orb Header Panel
        orb_panel = QFrame()
        orb_panel.setObjectName("OrbPanel")
        orb_layout = QVBoxLayout(orb_panel)
        orb_layout.setContentsMargins(0, 0, 0, 0)
        orb_layout.setSpacing(8)

        self.voice_orb = VoiceOrb()
        orb_layout.addWidget(self.voice_orb, alignment=Qt.AlignCenter)

        # Subtitle Status
        self.status_sublabel = QLabel("Tap orb or speak to begin")
        self.status_sublabel.setAlignment(Qt.AlignCenter)
        self.status_sublabel.setStyleSheet("color: #938ea1; font-size: 13px;")
        orb_layout.addWidget(self.status_sublabel)

        layout.addWidget(orb_panel)

        # 2. Conversation Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_layout.setSpacing(12)
        self.chat_layout.addStretch()

        self.scroll_area.setWidget(self.chat_container)
        layout.addWidget(self.scroll_area)

        # 3. Quick Action Chips Row
        chips_frame = QFrame()
        chips_layout = QHBoxLayout(chips_frame)
        chips_layout.setContentsMargins(0, 0, 0, 0)
        chips_layout.setSpacing(10)
        chips_layout.addStretch()

        for chip_text in self.CHIPS:
            btn = QPushButton(chip_text)
            btn.setObjectName("ChipButton")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, t=chip_text: self.controller.submit_text_command(t))
            chips_layout.addWidget(btn)

        chips_layout.addStretch()
        layout.addWidget(chips_frame)

        # 4. Bottom Command Input Bar
        self.input_bar = CommandInputBar()
        self.input_bar.sig_submit.connect(self.controller.submit_text_command)
        self.input_bar.sig_mic_toggle.connect(self.controller.trigger_voice_turn)

        layout.addWidget(self.input_bar)

        # Connect controller signals
        self.controller.sig_command_received.connect(self._on_user_command)
        self.controller.sig_response_ready.connect(self._on_astra_response)
        self.controller.sig_voice_state_changed.connect(self._on_voice_state)

        # Add initial welcome message
        self.add_message("ASTRA", "Hello! I am ASTRA, your personal AI computer assistant. How can I help you today?")

    def add_message(self, sender: str, text: str) -> None:
        """Append a message bubble to conversation."""
        bubble = MessageBubble(sender=sender, text=text)
        count = self.chat_layout.count()
        self.chat_layout.insertWidget(count - 1, bubble)

        # Auto-scroll to bottom
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

    def _on_user_command(self, text: str) -> None:
        self.add_message("You", text)

    def _on_astra_response(self, response_text: str, result: ToolResult | None) -> None:
        self.add_message("ASTRA", response_text)

    def _on_voice_state(self, state: str) -> None:
        self.voice_orb.set_state(state)
        state_str = str(state).upper()
        if "LISTENING" in state_str:
            self.status_sublabel.setText("Listening... Speak your command")
        elif "PROCESSING" in state_str:
            self.status_sublabel.setText("Thinking & processing...")
        elif "SPEAKING" in state_str:
            self.status_sublabel.setText("ASTRA is speaking")
        else:
            self.status_sublabel.setText("Tap mic or type a command")
