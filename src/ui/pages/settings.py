"""
Settings Page Component (Stitch Design System Integration).
Aligns with Stitch "Settings" design screen.
Provides UI configuration for LLM, Voice, Security, and System Settings.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFormLayout, QFrame, QLabel, QPushButton, QVBoxLayout, QWidget
from src.core.version import __version__, APP_FULL_NAME
from src.ui.controllers.app_controller import AppController
from src.ui.theme.manager import ThemeManager


class SettingsPage(QWidget):
    """Configuration Settings View matching Stitch design system."""

    def __init__(self, controller: AppController, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self.theme_manager = ThemeManager()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(20)

        title = QLabel("Settings & Configuration")
        title.setStyleSheet("font-size: 24px; font-weight: 700; color: #e2e2e3;")
        layout.addWidget(title)

        # Appearance Group
        card_app = QFrame()
        card_app.setProperty("class", "CardWidget")
        app_form = QFormLayout(card_app)

        app_title = QLabel("Appearance & Theme")
        app_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #7c5cfc;")
        app_form.addRow(app_title)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark (Calm Presence)"])
        self.theme_combo.setStyleSheet("background: #1a1c1d; color: #e2e2e3; border: 1px solid #484555; border-radius: 16px; padding: 8px 14px;")
        app_form.addRow("Theme Mode:", self.theme_combo)

        layout.addWidget(card_app)

        # Voice Subsystem Settings Group
        card_voice = QFrame()
        card_voice.setProperty("class", "CardWidget")
        v_form = QFormLayout(card_voice)

        v_title = QLabel("Voice & Speech Configuration")
        v_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #7c5cfc;")
        v_form.addRow(v_title)

        # STT Provider readout
        stt_lbl = QLabel(self.controller.voice_manager.voice_config.stt_provider)
        stt_lbl.setStyleSheet("font-weight: 700; color: #34d399;")
        v_form.addRow("STT Engine:", stt_lbl)

        # TTS Provider readout
        tts_lbl = QLabel(self.controller.voice_manager.voice_config.tts_provider)
        tts_lbl.setStyleSheet("font-weight: 700; color: #34d399;")
        v_form.addRow("TTS Engine:", tts_lbl)

        # Mic Device
        diag = self.controller.voice_manager.get_diagnostics()
        mic_lbl = QLabel(f"{diag.device_name} ({diag.status})")
        mic_lbl.setStyleSheet("color: #e2e2e3;")
        v_form.addRow("Input Microphone:", mic_lbl)

        layout.addWidget(card_voice)

        # LLM Brain & Security Group
        card_brain = QFrame()
        card_brain.setProperty("class", "CardWidget")
        b_form = QFormLayout(card_brain)

        b_title = QLabel("Brain Reasoning & Security Policy")
        b_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #7c5cfc;")
        b_form.addRow(b_title)

        llm_lbl = QLabel(f"{self.controller.agent.config.llm_provider.upper()} ({self.controller.agent.config.llm_model})")
        llm_lbl.setStyleSheet("font-weight: 700; color: #cebdff;")
        b_form.addRow("LLM Provider:", llm_lbl)

        sec_lbl = QLabel("NORMAL (Allowlisted & Permission Checked)")
        sec_lbl.setStyleSheet("font-weight: 700; color: #34d399;")
        b_form.addRow("Security Mode:", sec_lbl)

        layout.addWidget(card_brain)

        # About Group
        card_about = QFrame()
        card_about.setProperty("class", "CardWidget")
        ab_layout = QVBoxLayout(card_about)

        ab_title = QLabel(f"About {APP_FULL_NAME}")
        ab_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #7c5cfc;")
        ab_body = QLabel(f"ASTRA v{__version__} — Release Build\nStitch Design System ('Calm Presence' Theme)\nBuilt with Python & PySide6\nGoogle DeepMind Assistant Architecture")
        ab_body.setStyleSheet("font-size: 13px; color: #c9c4d8; line-height: 1.5;")

        ab_layout.addWidget(ab_title)
        ab_layout.addWidget(ab_body)

        layout.addWidget(card_about)
        layout.addStretch()
