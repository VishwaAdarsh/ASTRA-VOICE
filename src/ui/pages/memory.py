"""
Memory Page Component Placeholder (Phase 7 Preview).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class MemoryPage(QWidget):
    """Memory Subsystem Placeholder View."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        card = QFrame()
        card.setProperty("class", "CardWidget")
        c_layout = QVBoxLayout(card)
        c_layout.setAlignment(Qt.AlignCenter)

        title = QLabel("🧠 Memory Subsystem")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #38BDF8;")

        desc = QLabel("Personal memory, knowledge base embeddings, and episodic history will be introduced in Phase 7.")
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 14px; color: #94A3B8; margin-top: 10px;")

        c_layout.addWidget(title)
        c_layout.addWidget(desc)

        layout.addStretch()
        layout.addWidget(card)
        layout.addStretch()
