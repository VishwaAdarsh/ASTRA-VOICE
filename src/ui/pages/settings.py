"""
Settings Page Component.
Provides UI control for General, Voice, and Theme configurations.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFormLayout, QFrame, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget
from src.ui.controllers.app_controller import AppController
from src.ui.theme.manager import ThemeManager


class SettingsPage(QWidget):
    """Configuration Settings View."""

    def __init__(self, controller: AppController, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self.theme_manager = ThemeManager()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        title = QLabel("Settings")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #F8FAFC;")
        layout.addWidget(title)

        # Appearance Group
        card_app = QFrame()
        card_app.setProperty("class", "CardWidget")
        app_form = QFormLayout(card_app)

        app_title = QLabel("Appearance")
        app_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #38BDF8;")
        app_form.addRow(app_title)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light"])
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        app_form.addRow("Theme Mode:", self.theme_combo)

        layout.addWidget(card_app)

        # Voice Subsystem Settings Group
        card_voice = QFrame()
        card_voice.setProperty("class", "CardWidget")
        v_form = QFormLayout(card_voice)

        v_title = QLabel("Voice & Speech Configuration")
        v_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #38BDF8;")
        v_form.addRow(v_title)

        # STT Provider readout
        stt_lbl = QLabel(self.controller.voice_manager.voice_config.stt_provider)
        stt_lbl.setStyleSheet("font-weight: bold; color: #10B981;")
        v_form.addRow("STT Engine:", stt_lbl)

        # TTS Provider readout
        tts_lbl = QLabel(self.controller.voice_manager.voice_config.tts_provider)
        tts_lbl.setStyleSheet("font-weight: bold; color: #10B981;")
        v_form.addRow("TTS Engine:", tts_lbl)

        # Mic Device
        diag = self.controller.voice_manager.get_diagnostics()
        mic_lbl = QLabel(f"{diag.device_name} ({diag.status})")
        v_form.addRow("Input Microphone:", mic_lbl)

        layout.addWidget(card_voice)

        # About Group
        card_about = QFrame()
        card_about.setProperty("class", "CardWidget")
        ab_layout = QVBoxLayout(card_about)

        ab_title = QLabel("About ASTRA")
        ab_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #38BDF8;")
        ab_body = QLabel("ASTRA v0.3.0 (Phase 3 Desktop GUI)\nBuilt with Python & PySide6\nModular Allowlisted Operating System Assistant")
        ab_body.setStyleSheet("font-size: 12px; color: #94A3B8;")

        ab_layout.addWidget(ab_title)
        ab_layout.addWidget(ab_body)

        layout.addWidget(card_about)
        layout.addStretch()

    def _on_theme_changed(self, text: str) -> None:
        self.theme_manager.set_theme(text.lower())
