"""
Confirmation Dialog Modal.
Prompts user confirmation for CONFIRM security level tools.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class ConfirmationDialog(QDialog):
    """Modal dialog prompting confirmation before executing sensitive tools."""

    def __init__(self, action_description: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("ASTRA Security Confirmation")
        self.setFixedWidth(420)
        self.setWindowModality(Qt.ApplicationModal)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title = QLabel("Security Authorization Required")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #F59E0B;")

        desc = QLabel(f"ASTRA requires authorization to perform:\n\n'{action_description}'")
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 13px; color: #F8FAFC;")

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("IconButton")
        cancel_btn.clicked.connect(self.reject)

        confirm_btn = QPushButton("Confirm")
        confirm_btn.setStyleSheet("background-color: #10B981; color: white;")
        confirm_btn.clicked.connect(self.accept)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(confirm_btn)

        layout.addWidget(title)
        layout.addWidget(desc)
        layout.addLayout(btn_layout)
