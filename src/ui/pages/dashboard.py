"""
Dashboard Page Component (Stitch Design System Integration).
Aligns with Stitch Status & Health overview using real backend subsystem health states.
"""

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from src.ui.controllers.app_controller import AppController


class DashboardPage(QWidget):
    """Home Dashboard View (Stitch Status & Health Overview)."""

    sig_quick_action = Signal(str)

    def __init__(self, controller: AppController, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(20)

        # Header Greeting
        greeting = QLabel("ASTRA Assistant")
        greeting.setStyleSheet("font-size: 26px; font-weight: 700; color: #e2e2e3;")
        philosophy = QLabel("Calm Presence — Understand. Think. Act. Remember. See. Plan. Proact.")
        philosophy.setStyleSheet("font-size: 13px; color: #7c5cfc; font-weight: 500;")

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
        c1_title.setStyleSheet("font-size: 12px; color: #938ea1; text-transform: uppercase; font-weight: 600;")
        self.c1_status = QLabel("● Ready")
        self.c1_status.setStyleSheet("font-size: 18px; font-weight: 700; color: #34d399;")
        c1_layout.addWidget(c1_title)
        c1_layout.addWidget(self.c1_status)

        # Card 2: Voice System
        card2 = QFrame()
        card2.setProperty("class", "CardWidget")
        c2_layout = QVBoxLayout(card2)
        c2_title = QLabel("Voice Subsystem")
        c2_title.setStyleSheet("font-size: 12px; color: #938ea1; text-transform: uppercase; font-weight: 600;")
        self.c2_status = QLabel("🎙 Ready")
        self.c2_status.setStyleSheet("font-size: 18px; font-weight: 700; color: #7c5cfc;")
        c2_layout.addWidget(c2_title)
        c2_layout.addWidget(self.c2_status)

        # Card 3: Security Policy
        card3 = QFrame()
        card3.setProperty("class", "CardWidget")
        c3_layout = QVBoxLayout(card3)
        c3_title = QLabel("Security Boundary")
        c3_title.setStyleSheet("font-size: 12px; color: #938ea1; text-transform: uppercase; font-weight: 600;")
        c3_status = QLabel("NORMAL (Allowlisted)")
        c3_status.setStyleSheet("font-size: 16px; font-weight: 700; color: #e2e2e3;")
        c3_layout.addWidget(c3_title)
        c3_layout.addWidget(c3_status)

        grid.addWidget(card1, 0, 0)
        grid.addWidget(card2, 0, 1)
        grid.addWidget(card3, 0, 2)

        layout.addLayout(grid)

        # Health Subsystem Grid Header
        health_hdr = QLabel("Subsystem Health Indicators")
        health_hdr.setStyleSheet("font-size: 16px; font-weight: 700; color: #e2e2e3; margin-top: 10px;")
        layout.addWidget(health_hdr)

        health_grid = QGridLayout()
        health_grid.setSpacing(12)

        health_dict = self.controller.agent.health_manager.get_all_health()
        col = 0
        row = 0
        for sub_name, sub_health in health_dict.items():
            h_card = QFrame()
            h_card.setProperty("class", "CardWidget")
            h_layout = QHBoxLayout(h_card)
            h_layout.setContentsMargins(14, 10, 14, 10)

            lbl_name = QLabel(sub_name.upper())
            lbl_name.setStyleSheet("font-weight: 600; font-size: 13px; color: #c9c4d8;")

            st_val = sub_health.status.value if hasattr(sub_health.status, "value") else str(sub_health.status)
            color = "#34d399" if "HEALTHY" in st_val.upper() else "#fbbf24" if "DEGRADED" in st_val.upper() else "#ffb4ab"
            lbl_val = QLabel(f"● {st_val.capitalize()}")
            lbl_val.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {color};")

            h_layout.addWidget(lbl_name)
            h_layout.addStretch()
            h_layout.addWidget(lbl_val)


            health_grid.addWidget(h_card, row, col)
            col += 1
            if col >= 3:
                col = 0
                row += 1

        layout.addLayout(health_grid)

        # Quick Actions Header
        qa_label = QLabel("Quick Actions")
        qa_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #e2e2e3; margin-top: 10px;")
        layout.addWidget(qa_label)

        qa_layout = QHBoxLayout()
        qa_layout.setSpacing(12)

        btn_calc = QPushButton("Open Calculator")
        btn_calc.clicked.connect(lambda: self.controller.submit_text_command("open calculator"))

        btn_downloads = QPushButton("Open Downloads")
        btn_downloads.clicked.connect(lambda: self.controller.submit_text_command("open downloads"))

        btn_yt = QPushButton("Open YouTube")
        btn_yt.clicked.connect(lambda: self.controller.submit_text_command("open youtube"))

        btn_sys = QPushButton("System Info")
        btn_sys.clicked.connect(lambda: self.controller.submit_text_command("show system information"))

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
