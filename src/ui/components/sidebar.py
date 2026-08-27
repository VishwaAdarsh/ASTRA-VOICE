"""
Fluent Sidebar Navigation Component (Stitch Design System Integration).
Pill-shaped glassmorphic desktop navigation matching the "Calm Presence" aesthetic.
"""

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget
from src.ui.theme.tokens import DARK_PALETTE


class SidebarNav(QFrame):
    """Sidebar navigation panel matching Stitch design system."""

    sig_page_selected = Signal(int)

    NAV_ITEMS = [
        ("Dashboard", 0),
        ("Assistant", 1),
        ("Activity", 2),
        ("Tools", 3),
        ("Memory", 4),
        ("Vision", 5),
        ("Tasks", 6),
        ("Automations", 7),
        ("Settings", 8),
    ]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 24, 16, 24)
        layout.setSpacing(6)

        # ASTRA Header Branding
        brand_label = QLabel("ASTRA")
        brand_label.setStyleSheet("font-size: 22px; font-weight: 700; color: #7c5cfc; letter-spacing: 2px;")
        subtitle = QLabel("Personal AI Assistant")
        subtitle.setStyleSheet("font-size: 12px; color: #938ea1; margin-bottom: 24px;")

        layout.addWidget(brand_label)
        layout.addWidget(subtitle)

        # Navigation Buttons
        self.buttons: list[QPushButton] = []
        for title, index in self.NAV_ITEMS:
            btn = QPushButton(f"  {title}")
            btn.setObjectName("SidebarButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, idx=index: self._on_btn_clicked(idx))
            layout.addWidget(btn)
            self.buttons.append(btn)

        layout.addStretch()

        # Select Dashboard by default
        self.select_page(0)

    def _on_btn_clicked(self, page_index: int) -> None:
        self.select_page(page_index)
        self.sig_page_selected.emit(page_index)

    def select_page(self, page_index: int) -> None:
        for idx, btn in enumerate(self.buttons):
            btn.setChecked(idx == page_index)
