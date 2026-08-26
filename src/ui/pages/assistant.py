"""
Assistant Conversation Page Component.
Integrates VoiceOrb visualizer, conversation message bubbles, and command input bar.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget
from src.brain.models import ToolResult
from src.ui.components.command_input import CommandInputBar
from src.ui.components.message_bubble import MessageBubble
from src.ui.components.voice_orb import VoiceOrb
from src.ui.controllers.app_controller import AppController


class AssistantPage(QWidget):
    """Primary Assistant Interaction View."""

    def __init__(self, controller: AppController, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # 1. Top Voice Orb Panel
        orb_panel = QFrame()
        orb_panel.setObjectName("OrbPanel")
        orb_layout = QHBoxLayout(orb_panel)
        orb_layout.setContentsMargins(0, 0, 0, 0)
        
        self.voice_orb = VoiceOrb()
        orb_layout.addStretch()
        orb_layout.addWidget(self.voice_orb)
        orb_layout.addStretch()

        layout.addWidget(orb_panel)

        # 2. Conversation Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_layout.setSpacing(10)
        self.chat_layout.addStretch()

        self.scroll_area.setWidget(self.chat_container)
        layout.addWidget(self.scroll_area)

        # 3. Bottom Command Input Bar
        self.input_bar = CommandInputBar()
        self.input_bar.sig_submit.connect(self.controller.submit_text_command)
        self.input_bar.sig_mic_toggle.connect(self.controller.trigger_voice_turn)

        layout.addWidget(self.input_bar)

        # Connect controller signals
        self.controller.sig_command_received.connect(self._on_user_command)
        self.controller.sig_response_ready.connect(self._on_astra_response)
        self.controller.sig_voice_state_changed.connect(self.voice_orb.set_state)

        # Add initial welcome message
        self.add_message("ASTRA", "Hello! I am ASTRA, your personal AI computer assistant. How can I help you today?")

    def add_message(self, sender: str, text: str) -> None:
        """Append a message bubble to conversation."""
        bubble = MessageBubble(sender=sender, text=text)
        # Insert before stretch item
        count = self.chat_layout.count()
        self.chat_layout.insertWidget(count - 1, bubble)

        # Scroll to bottom
        QFrame().thread().msleep(10) if hasattr(QFrame().thread(), "msleep") else None
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

    def _on_user_command(self, text: str) -> None:
        self.add_message("You", text)

    def _on_astra_response(self, response_text: str, result: ToolResult | None) -> None:
        self.add_message("ASTRA", response_text)
