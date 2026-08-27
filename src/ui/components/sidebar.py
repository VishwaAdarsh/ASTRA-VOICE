"""
Fluent Sidebar Navigation Component.
"""

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget
from src.ui.theme.tokens import DARK_PALETTE


class SidebarNav(QFrame):
    """Sidebar navigation panel."""

    sig_page_selected = Signal(int)  # Page index signal

    NAV_ITEMS = [
        ("Dashboard", 0),
        ("Assistant", 1),
        ("Activity", 2),
        ("Tools", 3),
        ("Memory", 4),
        ("Vision", 5),
        ("Tasks", 6),
        ("Settings", 7),
    ]



    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 20, 12, 20)
        layout.setSpacing(8)

        # ASTRA Header Branding
        brand_label = QLabel("ASTRA")
        brand_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #38BDF8; letter-spacing: 2px;")
        subtitle = QLabel("AI Computer Assistant")
        subtitle.setStyleSheet("font-size: 11px; color: #94A3B8; margin-bottom: 20px;")

        layout.addWidget(brand_label)
        layout.addWidget(subtitle)

        # Navigation Buttons
        self.buttons: list[QPushButton] = []
        for title, index in self.NAV_ITEMS:
            btn = QPushButton(title)
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
