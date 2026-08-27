"""
Automation Manager Central Orchestrator.
Coordinates proactive rule parsing, validation, scheduling, evaluation, execution, and emergency stop.
"""

import uuid
from datetime import datetime
from src.core.config import Config
from src.core.exceptions import AutomationError
from src.core.logger import get_logger
from src.automation.evaluator import ConditionEvaluator
from src.automation.models import (
    ActionType,
    Automation,
    AutomationAction,
    AutomationDraft,
    AutomationResult,
    AutomationRun,
    AutomationStatus,
    Condition,
    ConditionType,
    NotificationPriority,
    RunStatus,
    TriggerType,
)
from src.automation.notification import NotificationManager
from src.automation.parser import AutomationParser
from src.automation.repository import AutomationRepository
from src.automation.scheduler import SchedulerManager
from src.automation.validator import AutomationValidator
from src.task.manager import TaskManager
from src.tools.registry import ToolRegistry

logger = get_logger()


class AutomationManager:
    """Central Orchestrator for Proactive Personal Assistant Automations."""

    def __init__(
        self,
        config: Config | None = None,
        registry: ToolRegistry | None = None,
        task_manager: TaskManager | None = None,
        repository: AutomationRepository | None = None,
        parser: AutomationParser | None = None,
        validator: AutomationValidator | None = None,
        evaluator: ConditionEvaluator | None = None,
        scheduler: SchedulerManager | None = None,
        notification_manager: NotificationManager | None = None,
    ):
        self.config = config or Config()
        self.registry = registry or ToolRegistry()
        self.task_manager = task_manager or TaskManager(config=self.config, registry=self.registry)
        self.repository = repository or AutomationRepository(config=self.config)
        self.parser = parser or AutomationParser(config=self.config)
        self.validator = validator or AutomationValidator(config=self.config, registry=self.registry)
        self.evaluator = evaluator or ConditionEvaluator(config=self.config)
        self.scheduler = scheduler or SchedulerManager(config=self.config)
        self.notification_manager = notification_manager or NotificationManager(config=self.config, repository=self.repository)

    def create_automation_from_text(self, natural_language_request: str) -> Automation:
        """Parse natural language request, validate, persist, and schedule proactive automation."""
        draft = self.parser.parse_request(natural_language_request)
        active_list = self.repository.list_automations(status=AutomationStatus.ACTIVE)
        self.validator.validate_draft(draft, active_count=len(active_list))

        auto_id = f"auto_{uuid.uuid4().hex[:8]}"

        cond = Condition(type=ConditionType(draft.condition_config["type"]), parameters=draft.condition_config.get("parameters", {})) if draft.condition_config and "type" in draft.condition_config else None
        act = AutomationAction(type=ActionType(draft.action_config["type"]), tool=draft.action_config.get("tool", "system_info"), arguments=draft.action_config.get("arguments", {}))

        auto = Automation(
            id=auto_id,
            name=draft.name,
            description=draft.description,
            status=AutomationStatus.ACTIVE,
            trigger_type=draft.trigger_type,
            trigger_config=draft.trigger_config,
            condition=cond,
            action=act,
        )

        self.repository.save_automation(auto)
        logger.info(f"AutomationManager created automation #{auto_id}: '{auto.name}'")

        # Schedule background execution
        delay = float(draft.trigger_config.get("interval_sec", 1))
        self.scheduler.schedule_automation(auto, callback=self.trigger_automation, delay_sec=delay)

        return auto

    def trigger_automation(self, auto_id: str) -> AutomationResult:
        """Trigger and execute an automation rule."""
        auto = self.repository.get_automation(auto_id)
        if not auto or auto.status != AutomationStatus.ACTIVE:
            return AutomationResult(automation_id=auto_id, status=RunStatus.SKIPPED, summary="Automation inactive or deleted.")

        # Check Quiet Hours
        if self.scheduler.is_quiet_hours():
            logger.info(f"Automation #{auto_id} triggered during QUIET HOURS. Delaying non-critical action.")
            return AutomationResult(automation_id=auto_id, status=RunStatus.SKIPPED, summary="Action delayed due to quiet hours.")

        run = AutomationRun(automation_id=auto_id, status=RunStatus.EXECUTING)
        self.repository.save_run(run)

        # Condition Check
        if auto.condition:
            run.status = RunStatus.EVALUATING
            if not self.evaluator.evaluate(auto.condition):
                run.status = RunStatus.SKIPPED
                run.result_summary = "Condition evaluated to FALSE."
                self.repository.save_run(run)
                return AutomationResult(automation_id=auto_id, status=RunStatus.SKIPPED, summary="Condition evaluated to FALSE.")

        # Action Execution
        run.status = RunStatus.EXECUTING
        notif_sent = False
        summary = "Action executed."

        try:
            if auto.action:
                if auto.action.type == ActionType.NOTIFY:
                    msg = str(auto.action.arguments.get("message", auto.name))
                    self.notification_manager.create_notification(title=f"Notification: {auto.name}", message=msg, source_automation_id=auto.id)
                    notif_sent = True
                    summary = f"Notification delivered: '{msg}'"

                elif auto.action.type in (ActionType.RUN_APPROVED_TASK, ActionType.RUN_RESEARCH):
                    task_res = self.task_manager.create_and_execute_goal(auto.name)
                    summary = f"Task completed: {task_res.summary}"

            run.status = RunStatus.COMPLETED
            run.completed_at = datetime.now().isoformat()
            run.result_summary = summary
            self.repository.save_run(run)

            auto.last_run_at = datetime.now().isoformat()
            auto.run_count += 1
            self.repository.save_automation(auto)

            return AutomationResult(automation_id=auto_id, status=RunStatus.COMPLETED, summary=summary, notification_sent=notif_sent)

        except Exception as e:
            logger.error(f"Automation #{auto_id} execution failed: {e}")
            run.status = RunStatus.FAILED
            run.completed_at = datetime.now().isoformat()
            run.error_message = str(e)
            self.repository.save_run(run)

            auto.failure_count += 1
            self.repository.save_automation(auto)

            return AutomationResult(automation_id=auto_id, status=RunStatus.FAILED, summary="Execution failed", error_message=str(e))

    def run_now(self, auto_id: str) -> AutomationResult:
        """Manually trigger immediate execution of an automation rule."""
        return self.trigger_automation(auto_id)

    def pause_automation(self, auto_id: str) -> bool:
        """Pause active automation rule."""
        auto = self.repository.get_automation(auto_id)
        if auto:
            auto.status = AutomationStatus.PAUSED
            self.repository.save_automation(auto)
            self.scheduler.cancel_automation(auto_id)
            return True
        return False

    def resume_automation(self, auto_id: str) -> bool:
        """Resume paused automation rule."""
        auto = self.repository.get_automation(auto_id)
        if auto:
            auto.status = AutomationStatus.ACTIVE
            self.repository.save_automation(auto)
            self.scheduler.schedule_automation(auto, callback=self.trigger_automation, delay_sec=1.0)
            return True
        return False

    def delete_automation(self, auto_id: str) -> bool:
        """Delete an automation rule."""
        self.scheduler.cancel_automation(auto_id)
        return self.repository.delete_automation(auto_id)

    def stop_all_automations(self) -> None:
        """Emergency Stop: pause all active automations and cancel scheduling timers."""
        logger.warning("AutomationManager triggering GLOBAL EMERGENCY STOP!")
        self.scheduler.cancel_all()
        for auto in self.repository.list_automations(status=AutomationStatus.ACTIVE):
            auto.status = AutomationStatus.PAUSED
            self.repository.save_automation(auto)

    def list_automations(self) -> list[Automation]:
        """List all persisted automations."""
        return self.repository.list_automations()
