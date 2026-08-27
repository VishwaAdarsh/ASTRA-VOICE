"""
Task Manager Central Orchestrator.
Coordinates planning, validation, execution, confirmation, emergency stop, and crash recovery.
"""

import uuid
from src.core.config import Config
from src.core.exceptions import ConfirmationRequiredError, PlanValidationError, TaskCancelledError, TaskEngineError
from src.core.logger import get_logger
from src.task.executor import TaskExecutor
from src.task.models import AutonomyLevel, Task, TaskResult, TaskStatus
from src.task.planner import TaskPlanner
from src.task.repository import TaskRepository
from src.task.validator import PlanValidator
from src.tools.registry import ToolRegistry


logger = get_logger()


class TaskManager:
    """Central Task Engine Orchestrator."""

    def __init__(
        self,
        config: Config | None = None,
        registry: ToolRegistry | None = None,
        repository: TaskRepository | None = None,
        planner: TaskPlanner | None = None,
        validator: PlanValidator | None = None,
        executor: TaskExecutor | None = None,
    ):
        self.config = config or Config()
        self.registry = registry or ToolRegistry()
        self.repository = repository or TaskRepository(config=self.config)
        self.planner = planner or TaskPlanner(config=self.config)
        self.validator = validator or PlanValidator(config=self.config, registry=self.registry)
        self.executor = executor or TaskExecutor(config=self.config, registry=self.registry, repository=self.repository)

        self._active_task: Task | None = None
        self._replan_counts: dict[str, int] = {}

    def create_and_execute_goal(self, goal: str) -> TaskResult:
        """Create structured task plan from goal, validate, and execute."""
        if self._active_task and self._active_task.status in (TaskStatus.EXECUTING, TaskStatus.PLANNING, TaskStatus.VERIFYING):
            raise TaskEngineError(f"Another task #{self._active_task.id} is currently running. Single task concurrency enforced.")

        task_id = f"task_{uuid.uuid4().hex[:8]}"
        logger.info(f"TaskManager starting new goal #{task_id}: '{goal}'")

        task = Task(id=task_id, goal=goal, status=TaskStatus.PLANNING)
        self._active_task = task
        self._replan_counts[task_id] = 0

        # 1. Planning Phase
        plan = self.planner.generate_plan(goal)
        task.plan = plan

        # 2. Validation Phase
        self.validator.validate_plan(plan, current_replan_count=self._replan_counts[task_id])
        self.repository.save_task(task)

        # 3. Execution Phase
        try:
            executed_task = self.executor.execute_task(task)
            return self._build_result(executed_task)
        except ConfirmationRequiredError as e:
            task.status = TaskStatus.AWAITING_CONFIRMATION
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.AWAITING_CONFIRMATION,
                summary=f"Task paused: {e}",
                completed_steps=task.current_step_index,
                total_steps=len(plan.steps),
                error_message=str(e),
            )
        except TaskCancelledError as e:
            task.status = TaskStatus.CANCELLED
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.CANCELLED,
                summary="Task execution was stopped by user emergency stop.",
                completed_steps=task.current_step_index,
                total_steps=len(plan.steps),
                error_message=str(e),
            )

    def confirm_and_resume(self, task_id: str) -> TaskResult:
        """Confirm high-risk action and resume paused task execution."""
        task = self.repository.get_task(task_id)
        if not task or task.status != TaskStatus.AWAITING_CONFIRMATION:
            raise TaskEngineError(f"Task #{task_id} is not currently awaiting confirmation.")

        task.status = TaskStatus.EXECUTING
        self._active_task = task
        executed_task = self.executor.execute_task(task)
        return self._build_result(executed_task)

    def emergency_stop(self) -> None:
        """Trigger emergency stop cancellation across active task executor."""

        logger.warning("TaskManager triggering EMERGENCY STOP!")
        self.executor.request_cancel()
        if self._active_task:
            self._active_task.status = TaskStatus.CANCELLED
            self.repository.save_task(self._active_task)

    def pause_task(self, task_id: str) -> bool:
        """Pause active task execution."""
        if self._active_task and self._active_task.id == task_id:
            self._active_task.status = TaskStatus.PAUSED
            self.repository.save_task(self._active_task)
            return True
        return False

    def resume_task(self, task_id: str) -> TaskResult:
        """Resume paused task."""
        task = self.repository.get_task(task_id)
        if not task:
            raise TaskEngineError(f"Task #{task_id} not found.")

        task.status = TaskStatus.EXECUTING
        self._active_task = task
        executed_task = self.executor.execute_task(task)
        return self._build_result(executed_task)

    def get_active_task(self) -> Task | None:
        """Get currently active task."""
        return self._active_task

    def list_recent_tasks(self, limit: int = 10) -> list[Task]:
        """Retrieve recent task history."""
        return self.repository.list_tasks(limit=limit)

    def _build_result(self, task: Task) -> TaskResult:
        """Build TaskResult output struct."""
        total = len(task.plan.steps) if task.plan and task.plan.steps else 0
        completed = sum(1 for s in (task.plan.steps if task.plan else []) if s.status.value == "COMPLETED")

        return TaskResult(
            task_id=task.id,
            status=task.status,
            summary=task.result_summary or f"Task finished with status {task.status.value}",
            completed_steps=completed,
            total_steps=total,
            artifacts=task.artifacts,
            error_message=task.error_message,
        )
