"""
Unit tests for AutomationRepository and SQLite database persistence.
"""

from src.automation.models import ActionType, Automation, AutomationAction, AutomationRun, AutomationStatus, Notification, NotificationPriority, RunStatus, TriggerType
from src.automation.repository import AutomationRepository
from src.database.connection import DatabaseManager


def test_automation_repository_save_and_get(tmp_path):
    db_file = tmp_path / "test_automations.db"
    db_mgr = DatabaseManager(db_path=db_file)
    repo = AutomationRepository(db_manager=db_mgr)

    act = AutomationAction(type=ActionType.NOTIFY, tool="system_info", arguments={"message": "Test reminder"})
    auto = Automation(
        id="auto_123",
        name="Test Daily Reminder",
        status=AutomationStatus.ACTIVE,
        trigger_type=TriggerType.SCHEDULE,
        action=act,
    )

    repo.save_automation(auto)
    retrieved = repo.get_automation("auto_123")

    assert retrieved is not None
    assert retrieved.id == "auto_123"
    assert retrieved.name == "Test Daily Reminder"
    assert retrieved.status == AutomationStatus.ACTIVE
    assert retrieved.action is not None
    assert retrieved.action.type == ActionType.NOTIFY


def test_automation_repository_notifications(tmp_path):
    db_file = tmp_path / "test_automations.db"
    db_mgr = DatabaseManager(db_path=db_file)
    repo = AutomationRepository(db_manager=db_mgr)

    notif = Notification(id="notif_1", title="Test Title", message="Test Message", priority=NotificationPriority.NORMAL)
    repo.save_notification(notif)

    unread = repo.list_notifications(unread_only=True)
    assert len(unread) == 1
    assert unread[0].title == "Test Title"
