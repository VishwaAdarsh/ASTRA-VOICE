"""
Unit tests for NotificationManager.
"""

from src.automation.models import NotificationPriority
from src.automation.notification import NotificationManager
from src.automation.repository import AutomationRepository
from src.database.connection import DatabaseManager


def test_notification_manager_create_and_dismiss(tmp_path):
    db_file = tmp_path / "test_notif.db"
    db_mgr = DatabaseManager(db_path=db_file)
    repo = AutomationRepository(db_manager=db_mgr)
    nm = NotificationManager(repository=repo)

    notif = nm.create_notification(title="Daily Check", message="Time to review tasks", priority=NotificationPriority.HIGH)
    assert notif.id is not None

    unread = nm.list_unread()
    assert len(unread) == 1
    assert unread[0].id == notif.id

    dismissed = nm.dismiss_notification(notif.id)
    assert dismissed == True

    unread_after = nm.list_unread()
    assert len(unread_after) == 0
