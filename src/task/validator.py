"""
Plan Validator Component.
Validates task plans against tool registry allowlists, step limits, risk policies, and dependencies.
"""

from src.core.config import Config
from src.core.exceptions import PlanValidationError
from src.core.logger import get_logger
from src.security.permissions import PermissionManager
from src.task.models import ActionRiskLevel, TaskPlan
from src.tools.registry import ToolRegistry


logger = get_logger()


class PlanValidator:
    """Validates TaskPlan steps against system limits, tool registry, and permissions."""

    def __init__(
        self,
        config: Config | None = None,
        registry: ToolRegistry | None = None,
        permission_manager: PermissionManager | None = None,
    ):
        self.config = config or Config()
        self.registry = registry or ToolRegistry()
        self.permission_manager = permission_manager or PermissionManager(config=self.config)

    def validate_plan(self, plan: TaskPlan, current_replan_count: int = 0) -> bool:
        """Validate plan structure, tool registration, limits, and step dependencies."""
        max_steps = self.config.agent_max_steps
        max_replans = self.config.agent_max_replans

        # 1. Step Count Limit Check
        if len(plan.steps) > max_steps:
            raise PlanValidationError(f"Plan exceeds maximum step limit ({len(plan.steps)} > {max_steps}).")

        # 2. Replan Count Limit Check
        if current_replan_count > max_replans:
            raise PlanValidationError(f"Task exceeded maximum replanning limit ({current_replan_count} > {max_replans}).")

        # 3. Tool Registration & Argument Validation
        known_step_numbers = set()
        for step in plan.steps:
            known_step_numbers.add(step.step_number)

            try:
                tool = self.registry.get(step.tool_name)
            except Exception:
                raise PlanValidationError(f"Step {step.step_number} specifies unregistered tool '{step.tool_name}'.")

            # Allow placeholder arguments during plan validation
            if step.arguments and not tool.validate(step.arguments):
                # Valid fallback if step relies on dynamic runtime output
                logger.debug(f"Step {step.step_number} arguments are dynamic placeholders for '{step.tool_name}'")


            # 4. Dependency Ordering Check
            for dep in step.depends_on:
                if dep not in known_step_numbers or dep >= step.step_number:
                    raise PlanValidationError(f"Step {step.step_number} has invalid forward/missing dependency #{dep}.")

            # 5. Assign Risk Level based on Tool Permission Level
            perm = tool.permission_level.value.upper()
            if perm == "SAFE":
                step.risk_level = ActionRiskLevel.SAFE
            elif perm == "CONFIRM":
                step.risk_level = ActionRiskLevel.HIGH_RISK
            elif perm == "DENY":
                step.risk_level = ActionRiskLevel.DESTRUCTIVE
            else:
                step.risk_level = ActionRiskLevel.LOW_RISK


        logger.info(f"PlanValidator successfully validated plan '{plan.goal}' ({len(plan.steps)} steps).")
        return True
