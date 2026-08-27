"""
Crash Recovery Manager Component.
Detects interrupted tasks and automations on application startup, marks unsafe interrupted runs as INTERRUPTED, and restores safe scheduler state.
"""

from src.automation.manager import AutomationManager
from src.automation.models import AutomationStatus
from src.core.config import Config
from src.core.logger import get_logger
from src.task.manager import TaskManager
from src.task.models import TaskStatus

logger = get_logger()


class CrashRecoveryManager:
    """Handles startup system state audit and crash recovery."""

    def __init__(
        self,
        config: Config | None = None,
        task_manager: TaskManager | None = None,
        automation_manager: AutomationManager | None = None,
    ):
        self.config = config or Config()
        self.task_manager = task_manager
        self.automation_manager = automation_manager

    def perform_startup_recovery(self) -> dict[str, int]:
        """Audit persisted database states on startup and recover safely from unexpected shutdowns."""
        logger.info("CrashRecoveryManager auditing database states for crash recovery...")
        recovered_tasks = 0
        recovered_automations = 0

        # 1. Task Engine Recovery (mark running tasks as INTERRUPTED)
        if self.task_manager:
            try:
                active_tasks = self.task_manager.repository.list_tasks(status=TaskStatus.EXECUTING)
                for t in active_tasks:
                    t.status = TaskStatus.FAILED
                    t.error_message = "Task interrupted by system restart or crash."
                    self.task_manager.repository.save_task(t)
                    recovered_tasks += 1
                    logger.warning(f"Recovered interrupted task #{t.id} -> FAILED")
            except Exception as e:
                logger.error(f"Error during task engine crash recovery: {e}")

        # 2. Automation Engine Recovery (restore ACTIVE automations to scheduler)
        if self.automation_manager:
            try:
                active_autos = self.automation_manager.repository.list_automations(status=AutomationStatus.ACTIVE)
                for a in active_autos:
                    self.automation_manager.scheduler.schedule_automation(
                        a, callback=self.automation_manager.trigger_automation, delay_sec=5.0
                    )
                    recovered_automations += 1
                    logger.info(f"Restored background automation scheduler #{a.id} ('{a.name}')")
            except Exception as e:
                logger.error(f"Error during automation crash recovery: {e}")

        return {
            "recovered_tasks": recovered_tasks,
            "recovered_automations": recovered_automations,
        }
