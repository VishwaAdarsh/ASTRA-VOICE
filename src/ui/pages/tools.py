"""
Tools Registry Inspection Page Component.
Dynamically queries ToolRegistry to display approved allowlisted tools.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget
from src.ui.controllers.app_controller import AppController


class ToolsPage(QWidget):
    """Registered Tools Inspector Page."""

    def __init__(self, controller: AppController, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Approved Tool Registry")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #F8FAFC;")
        subtitle = QLabel("Only explicitly registered, allowlisted capabilities can be executed by ASTRA.")
        subtitle.setStyleSheet("font-size: 13px; color: #94A3B8;")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Dynamic Tools Grid
        self.grid = QGridLayout()
        self.grid.setSpacing(16)

        self.refresh_tools()

        layout.addLayout(self.grid)
        layout.addStretch()

    def refresh_tools(self) -> None:
        """Query ToolRegistry and render tool cards."""
        registry = self.controller.agent.registry
        tool_names = registry.list_tools()

        row, col = 0, 0
        for name in tool_names:
            tool = registry.get(name)

            card = QFrame()
            card.setProperty("class", "CardWidget")
            c_layout = QVBoxLayout(card)

            t_name = QLabel(f"⚙ {tool.name}")
            t_name.setStyleSheet("font-size: 16px; font-weight: bold; color: #38BDF8;")

            t_desc = QLabel(tool.description)
            t_desc.setWordWrap(True)
            t_desc.setStyleSheet("font-size: 12px; color: #94A3B8;")

            t_perm = QLabel(f"Permission Level: {tool.permission_level.value}")
            t_perm.setStyleSheet("font-size: 11px; font-weight: bold; color: #10B981;")

            c_layout.addWidget(t_name)
            c_layout.addWidget(t_desc)
            c_layout.addWidget(t_perm)

            self.grid.addWidget(card, row, col)
            col += 1
            if col >= 2:
                col = 0
                row += 1
