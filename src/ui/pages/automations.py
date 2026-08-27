"""
Proactive Automations & Reminders Page Component (Stitch Design System Integration).
Aligns with Stitch "Reminders List" design screen.
Connects to Phase 10 AutomationManager, background scheduler, and NotificationManager.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from src.automation.manager import AutomationManager
from src.automation.models import AutomationStatus
from src.core.logger import get_logger

logger = get_logger()


class AutomationsPage(QWidget):
    """Interactive Proactive Automations & Reminders Center matching Stitch design system."""

    def __init__(self, automation_manager: AutomationManager | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.automation_manager = automation_manager or AutomationManager()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(20)

        # Header & Emergency Stop
        header_layout = QHBoxLayout()

        title_lbl = QLabel("⏰ Proactive Automations & Reminders")
        title_lbl.setStyleSheet("font-size: 24px; font-weight: 700; color: #e2e2e3;")

        self.stop_btn = QPushButton("🛑 STOP ALL AUTOMATIONS")
        self.stop_btn.setFixedHeight(44)
        self.stop_btn.setStyleSheet("background: #ffb4ab; color: #690005; font-size: 14px; font-weight: 700; border-radius: 22px; padding: 0 22px;")
        self.stop_btn.clicked.connect(self._on_emergency_stop)

        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        header_layout.addWidget(self.stop_btn)

        # Quick Creation Card (Stitch Pill Input)
        create_card = QFrame()
        create_card.setProperty("class", "CardWidget")
        c_layout = QHBoxLayout(create_card)
        c_layout.setContentsMargins(16, 12, 16, 12)
        c_layout.setSpacing(12)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Create reminder/automation (e.g. 'Remind me tomorrow at 9 AM to review project')...")

        create_btn = QPushButton("➕ Create Automation")
        create_btn.setFixedHeight(44)
        create_btn.clicked.connect(self._on_create_automation)

        c_layout.addWidget(self.input_field, stretch=1)
        c_layout.addWidget(create_btn)

        # Split Layout (Left: Automations List; Right: Notifications Center)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)

        # Left Panel (Automations List)
        left_card = QFrame()
        left_card.setProperty("class", "CardWidget")
        l_layout = QVBoxLayout(left_card)

        l_title = QLabel("Active Automations & Schedules")
        l_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #7c5cfc;")

        self.auto_list = QListWidget()
        self.auto_list.setStyleSheet("background: #1a1c1d; color: #e2e2e3; border: none; border-radius: 12px; font-size: 14px; padding: 8px;")

        l_layout.addWidget(l_title)
        l_layout.addWidget(self.auto_list)

        # Right Panel (Notifications Badge Center)
        right_card = QFrame()
        right_card.setProperty("class", "CardWidget")
        r_layout = QVBoxLayout(right_card)

        r_title = QLabel("Notifications Center")
        r_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #fbbf24;")

        self.notif_list = QListWidget()
        self.notif_list.setStyleSheet("background: #1a1c1d; color: #e2e2e3; border: none; border-radius: 12px; font-size: 14px; padding: 8px;")

        r_layout.addWidget(r_title)
        r_layout.addWidget(self.notif_list)

        content_layout.addWidget(left_card, stretch=1)
        content_layout.addWidget(right_card, stretch=1)

        layout.addLayout(header_layout)
        layout.addWidget(create_card)
        layout.addLayout(content_layout, stretch=1)

        self.refresh_ui()

    def _on_create_automation(self):
        text = self.input_field.text().strip()
        if not text:
            return

        try:
            auto = self.automation_manager.create_automation_from_text(text)
            self.input_field.clear()
            self.refresh_ui()
        except Exception as e:
            logger.error(f"Failed to create automation: {e}")

    def refresh_ui(self):
        """Refresh lists for automations and unread notifications."""
        self.auto_list.clear()
        automations = self.automation_manager.list_automations()
        for a in automations:
            status_icon = "🟢" if a.status == AutomationStatus.ACTIVE else "🟡"
            item = QListWidgetItem(f"{status_icon} {a.name} [{a.trigger_type.value}] - Status: {a.status.value}")
            self.auto_list.addItem(item)

        self.notif_list.clear()
        notifs = self.automation_manager.notification_manager.list_unread()
        for n in notifs:
            item = QListWidgetItem(f"🔔 [{n.priority.value}] {n.title}: {n.message}")
            self.notif_list.addItem(item)

    def _on_emergency_stop(self):
        self.automation_manager.stop_all_automations()
        self.refresh_ui()
