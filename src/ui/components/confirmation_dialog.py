"""
Confirmation Dialog Modal (Stitch Design System Integration).
Aligns with Stitch "Confirmation States" design screen.
Prompts user confirmation for CONFIRM security level tools.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class ConfirmationDialog(QDialog):
    """Modal dialog prompting confirmation before executing sensitive tools."""

    def __init__(self, action_description: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("ASTRA Security Authorization")
        self.setFixedWidth(440)
        self.setWindowModality(Qt.ApplicationModal)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e2021;
                border: 1px solid #7c5cfc;
                border-radius: 16px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        title = QLabel("Security Authorization Required")
        title.setStyleSheet("font-size: 17px; font-weight: 700; color: #fbbf24;")

        desc = QLabel(f"ASTRA requires your authorization to perform the following action:\n\n'{action_description}'")
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 14px; color: #e2e2e3; line-height: 1.5;")

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.setSpacing(12)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("IconButton")
        cancel_btn.setMinimumWidth(100)
        cancel_btn.clicked.connect(self.reject)

        confirm_btn = QPushButton("Authorize Action")
        confirm_btn.setMinimumWidth(140)
        confirm_btn.setStyleSheet("background-color: #7c5cfc; color: white; font-weight: 700;")
        confirm_btn.clicked.connect(self.accept)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(confirm_btn)

        layout.addWidget(title)
        layout.addWidget(desc)
        layout.addLayout(btn_layout)
