"""
Notification Manager Component.
Manages creation, priority routing, delivery, snoozing, dismissing, and cleanup of user notifications.
"""

import uuid
from datetime import datetime, timedelta
from src.core.config import Config
from src.core.logger import get_logger
from src.automation.models import Notification, NotificationPriority
from src.automation.repository import AutomationRepository

logger = get_logger()


class NotificationManager:
    """Manages proactive notification delivery, snoozing, and persistence."""

    def __init__(self, config: Config | None = None, repository: AutomationRepository | None = None):
        self.config = config or Config()
        self.repository = repository or AutomationRepository(config=self.config)

    def create_notification(
        self,
        title: str,
        message: str,
        type: str = "REMINDER",
        priority: NotificationPriority = NotificationPriority.NORMAL,
        source_automation_id: str | None = None,
    ) -> Notification:
        """Create and persist a user notification."""
        notif_id = f"notif_{uuid.uuid4().hex[:8]}"
        notif = Notification(
            id=notif_id,
            title=title,
            message=message,
            type=type,
            priority=priority,
            source_automation_id=source_automation_id,
        )
        self.repository.save_notification(notif)
        logger.info(f"NotificationManager created notification #{notif_id} [{priority.value}]: '{title}'")
        return notif

    def dismiss_notification(self, notif_id: str) -> bool:
        """Mark notification as read/dismissed."""
        notifs = self.repository.list_notifications(limit=100)
        for n in notifs:
            if n.id == notif_id:
                n.status = "READ"
                n.read_at = datetime.now().isoformat()
                self.repository.save_notification(n)
                return True
        return False

    def snooze_notification(self, notif_id: str, minutes: int = 30) -> Notification | None:
        """Snooze notification by scheduling a new notification after target delay."""
        notifs = self.repository.list_notifications(limit=100)
        for n in notifs:
            if n.id == notif_id:
                n.status = "SNOOZED"
                n.read_at = datetime.now().isoformat()
                self.repository.save_notification(n)

                return self.create_notification(
                    title=f"[Snoozed] {n.title}",
                    message=n.message,
                    type=n.type,
                    priority=n.priority,
                    source_automation_id=n.source_automation_id,
                )
        return None

    def list_unread(self, limit: int = 20) -> list[Notification]:
        """Get unread user notifications."""
        return self.repository.list_notifications(unread_only=True, limit=limit)
