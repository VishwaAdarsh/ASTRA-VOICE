"""
Task Executor Engine.
Orchestrates sequential step execution, tool invocation, observations, retries, and emergency cancellation.
"""

import time
from pathlib import Path
from src.brain.models import ExecutionStatus, ToolRequest
from src.core.config import Config
from src.core.exceptions import ConfirmationRequiredError, TaskCancelledError, TaskExecutionError
from src.core.logger import get_logger

from src.execution.executor import ToolExecutor
from src.execution.verifier import ToolVerifier
from src.security.permissions import PermissionManager
from src.task.models import ActionRiskLevel, StepStatus, Task, TaskArtifact, TaskCheckpoint, TaskStatus, TaskStep
from src.task.repository import TaskRepository
from src.task.verifier import TaskVerifier
from src.tools.registry import ToolRegistry



logger = get_logger()


class TaskExecutor:
    """Executes multi-step task plans sequentially with retry, checkpoint, and cancellation support."""

    def __init__(
        self,
        config: Config | None = None,
        registry: ToolRegistry | None = None,
        permission_manager: PermissionManager | None = None,
        tool_executor: ToolExecutor | None = None,
        verifier: TaskVerifier | None = None,
        repository: TaskRepository | None = None,
    ):
        self.config = config or Config()
        self.registry = registry or ToolRegistry()
        self.permission_manager = permission_manager or PermissionManager(config=self.config)
        self.verifier = verifier or TaskVerifier(config=self.config)
        self.tool_executor = tool_executor or ToolExecutor(
            registry=self.registry,
            permission_manager=self.permission_manager,
            verifier=ToolVerifier(config=self.config),
        )
        self.repository = repository or TaskRepository(config=self.config)
        self._cancel_requested = False

    def request_cancel(self) -> None:
        """Signal emergency stop / task cancellation."""
        logger.warning("TaskExecutor received EMERGENCY CANCEL request!")
        self._cancel_requested = True

    def execute_task(self, task: Task) -> Task:
        """Execute task steps sequentially in bounded loop."""
        self._cancel_requested = False
        task.status = TaskStatus.EXECUTING
        task.started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        self.repository.save_task(task)
        self.repository.log_event(task.id, "TASK_STARTED", {"goal": task.goal})

        if not task.plan or not task.plan.steps:
            task.status = TaskStatus.FAILED
            task.error_message = "Task has no executable plan steps."
            self.repository.save_task(task)
            return task

        start_time = time.time()
        timeout = self.config.agent_timeout
        max_retries = self.config.agent_max_retries

        for idx, step in enumerate(task.plan.steps):
            task.current_step_index = idx

            # Check Cancellation
            if self._cancel_requested or task.status == TaskStatus.CANCELLED:
                step.status = StepStatus.CANCELLED
                task.status = TaskStatus.CANCELLED
                task.error_message = "Task execution was cancelled by user emergency stop."
                self.repository.save_task(task)
                self.repository.log_event(task.id, "TASK_CANCELLED", {"step": step.step_number})
                raise TaskCancelledError("Task execution cancelled.")

            # Check Timeout
            if time.time() - start_time > timeout:
                step.status = StepStatus.FAILED
                task.status = TaskStatus.FAILED
                task.error_message = f"Task execution exceeded timeout limit ({timeout}s)."
                self.repository.save_task(task)
                break

            # Check Risk Confirmation Gate
            if step.risk_level in (ActionRiskLevel.HIGH_RISK, ActionRiskLevel.DESTRUCTIVE):
                if task.status != TaskStatus.AWAITING_CONFIRMATION:
                    task.status = TaskStatus.AWAITING_CONFIRMATION
                    self.repository.save_task(task)
                    self.repository.log_event(task.id, "TASK_AWAITING_CONFIRMATION", {"step": step.step_number, "risk": step.risk_level.value})
                    raise ConfirmationRequiredError(f"Step {step.step_number} ({step.description}) requires user confirmation due to {step.risk_level.value} risk.")

            step.status = StepStatus.EXECUTING
            step.started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ")
            self.repository.save_task(task)

            # Step Retry Loop
            retry_count = 0
            step_success = False

            while retry_count <= max_retries:
                logger.info(f"TaskExecutor running Step {step.step_number}: '{step.description}' (attempt {retry_count + 1})")
                tool_request = ToolRequest(tool_name=step.tool_name, parameters=step.arguments)
                tool_res = self.tool_executor.execute(tool_request)

                # Verification Phase

                task.status = TaskStatus.VERIFYING
                ver_res = self.verifier.verify_step(step, tool_res)

                if ver_res.success:
                    step.status = StepStatus.COMPLETED
                    step.result_data = tool_res.data or {}
                    step.completed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                    step_success = True

                    # Track Artifact if file created
                    if "file_path" in step.arguments:
                        fp = str(step.arguments["file_path"])
                        task.artifacts.append(TaskArtifact(name=Path(fp).name, file_path=fp))

                    break
                else:
                    retry_count += 1
                    logger.warning(f"Step {step.step_number} verification failed: {ver_res.message}. Retrying ({retry_count}/{max_retries})...")
                    time.sleep(0.5)

            if not step_success:
                step.status = StepStatus.FAILED
                step.error_message = f"Step verification failed after {max_retries} retries."
                task.status = TaskStatus.FAILED
                task.error_message = f"Step {step.step_number} ('{step.description}') failed."
                self.repository.save_task(task)
                self.repository.log_event(task.id, "TASK_STEP_FAILED", {"step": step.step_number, "error": step.error_message})
                return task

            # Save Checkpoint after successful step
            checkpoint = TaskCheckpoint(
                task_id=task.id,
                step_number=step.step_number,
                state_json=f"{{\"step\": {step.step_number}, \"status\": \"COMPLETED\"}}",
                safe_to_resume=True,
            )
            self.repository.save_checkpoint(checkpoint)
            self.repository.log_event(task.id, "TASK_STEP_COMPLETED", {"step": step.step_number})

        # All Steps Completed Successfully
        task.status = TaskStatus.COMPLETED
        task.completed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        task.result_summary = f"Completed all {len(task.plan.steps)} steps for goal: '{task.goal}'"
        self.repository.save_task(task)
        self.repository.log_event(task.id, "TASK_COMPLETED", {"summary": task.result_summary})
        return task
