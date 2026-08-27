"""
Unit tests for CrashRecoveryManager.
"""

from src.automation.manager import AutomationManager
from src.automation.models import ActionType, Automation, AutomationAction, AutomationStatus, TriggerType
from src.automation.repository import AutomationRepository
from src.core.recovery import CrashRecoveryManager
from src.database.connection import DatabaseManager
from src.task.manager import TaskManager
from src.task.models import Task, TaskStatus
from src.task.repository import TaskRepository


def test_crash_recovery_manager(tmp_path):
    db_file = tmp_path / "test_recovery.db"
    db_mgr = DatabaseManager(db_path=db_file)

    task_repo = TaskRepository(db_manager=db_mgr)
    task_mgr = TaskManager(repository=task_repo)

    auto_repo = AutomationRepository(db_manager=db_mgr)
    auto_mgr = AutomationManager(repository=auto_repo, task_manager=task_mgr)

    # Insert an interrupted executing task
    t = Task(id="task_exec_1", goal="Search files", status=TaskStatus.EXECUTING)
    task_repo.save_task(t)

    # Insert an active automation
    a = Automation(
        id="auto_act_1",
        name="Daily Reminder",
        status=AutomationStatus.ACTIVE,
        trigger_type=TriggerType.SCHEDULE,
        action=AutomationAction(type=ActionType.NOTIFY),
    )
    auto_repo.save_automation(a)

    recovery = CrashRecoveryManager(task_manager=task_mgr, automation_manager=auto_mgr)
    res = recovery.perform_startup_recovery()

    assert res["recovered_tasks"] == 1
    assert res["recovered_automations"] == 1

    updated_t = task_repo.get_task("task_exec_1")
    assert updated_t is not None
    assert updated_t.status == TaskStatus.FAILED
    assert "interrupted" in updated_t.error_message.lower()
