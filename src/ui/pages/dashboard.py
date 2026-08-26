"""
Dashboard Page Component.
Displays user greeting, system state overview, voice status, and quick actions.
"""

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from src.ui.controllers.app_controller import AppController


class DashboardPage(QWidget):
    """Home Dashboard View."""

    sig_quick_action = Signal(str)

    def __init__(self, controller: AppController, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Header Greeting
        greeting = QLabel("Welcome to ASTRA")
        greeting.setStyleSheet("font-size: 24px; font-weight: bold; color: #F8FAFC;")
        philosophy = QLabel("Understand. Think. Act. Remember.")
        philosophy.setStyleSheet("font-size: 13px; color: #38BDF8; font-style: italic;")

        layout.addWidget(greeting)
        layout.addWidget(philosophy)

        # Status Cards Grid
        grid = QGridLayout()
        grid.setSpacing(16)

        # Card 1: Core State
        card1 = QFrame()
        card1.setProperty("class", "CardWidget")
        c1_layout = QVBoxLayout(card1)
        c1_title = QLabel("ASTRA Engine")
        c1_title.setStyleSheet("font-size: 12px; color: #94A3B8; text-transform: uppercase;")
        c1_status = QLabel("● Online")
        c1_status.setStyleSheet("font-size: 18px; font-weight: bold; color: #10B981;")
        c1_layout.addWidget(c1_title)
        c1_layout.addWidget(c1_status)

        # Card 2: Voice System
        card2 = QFrame()
        card2.setProperty("class", "CardWidget")
        c2_layout = QVBoxLayout(card2)
        c2_title = QLabel("Voice Subsystem")
        c2_title.setStyleSheet("font-size: 12px; color: #94A3B8; text-transform: uppercase;")
        self.c2_status = QLabel("🎙 Ready")
        self.c2_status.setStyleSheet("font-size: 18px; font-weight: bold; color: #38BDF8;")
        c2_layout.addWidget(c2_title)
        c2_layout.addWidget(self.c2_status)

        # Card 3: Security Mode
        card3 = QFrame()
        card3.setProperty("class", "CardWidget")
        c3_layout = QVBoxLayout(card3)
        c3_title = QLabel("Security Policy")
        c3_title.setStyleSheet("font-size: 12px; color: #94A3B8; text-transform: uppercase;")
        c3_status = QLabel("NORMAL (Allowlisted)")
        c3_status.setStyleSheet("font-size: 16px; font-weight: bold; color: #F8FAFC;")
        c3_layout.addWidget(c3_title)
        c3_layout.addWidget(c3_status)

        grid.addWidget(card1, 0, 0)
        grid.addWidget(card2, 0, 1)
        grid.addWidget(card3, 0, 2)

        layout.addLayout(grid)

        # Quick Actions Header
        qa_label = QLabel("Quick Actions")
        qa_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #F8FAFC; margin-top: 10px;")
        layout.addWidget(qa_label)

        qa_layout = QHBoxLayout()
        qa_layout.setSpacing(12)

        btn_calc = QPushButton("Open Calculator")
        btn_calc.clicked.connect(lambda: self.sig_quick_action.emit("open calculator"))

        btn_downloads = QPushButton("Open Downloads")
        btn_downloads.clicked.connect(lambda: self.sig_quick_action.emit("open downloads"))

        btn_yt = QPushButton("Open YouTube")
        btn_yt.clicked.connect(lambda: self.sig_quick_action.emit("open youtube"))

        btn_sys = QPushButton("System Info")
        btn_sys.clicked.connect(lambda: self.sig_quick_action.emit("show system information"))

        qa_layout.addWidget(btn_calc)
        qa_layout.addWidget(btn_downloads)
        qa_layout.addWidget(btn_yt)
        qa_layout.addWidget(btn_sys)
        qa_layout.addStretch()

        layout.addLayout(qa_layout)
        layout.addStretch()

        # Connect controller voice state signal
        self.controller.sig_voice_state_changed.connect(self._on_voice_state)

    def _on_voice_state(self, state: str) -> None:
        self.c2_status.setText(f"🎙 {state.capitalize()}")
