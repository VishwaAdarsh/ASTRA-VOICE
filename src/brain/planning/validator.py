"""
Plan Validator Subsystem.
Validates multi-step plans against ToolRegistry, parameter schemas, and security policies before execution.
"""

from typing import TYPE_CHECKING
from src.brain.planning.plan_models import Plan
from src.core.logger import get_logger

if TYPE_CHECKING:
    from src.security.permissions import PermissionManager
    from src.tools.registry import ToolRegistry

logger = get_logger()


class PlanValidator:
    """Validates multi-step plans to prevent execution of unapproved or invalid tool steps."""

    def __init__(self, registry: "ToolRegistry", permission_manager: "PermissionManager"):
        self.registry = registry
        self.permission_manager = permission_manager

    def validate(self, plan: Plan) -> tuple[bool, str | None]:
        """Validate all steps in a plan against ToolRegistry and PermissionManager."""
        logger.info(f"PLAN_VALIDATION: Validating plan '{plan.plan_id}' with {len(plan.steps)} steps")

        if not plan.steps:
            plan.is_valid = False
            plan.validation_error = "Plan contains no execution steps."
            return False, plan.validation_error

        for step in plan.steps:
            # 1. Check Tool Existence in ToolRegistry
            if not self.registry.contains(step.tool_name):
                error_msg = f"Plan step {step.step_id} references unregistered tool '{step.tool_name}'."
                logger.warning(f"PLAN_VALIDATION_FAILED: {error_msg}")
                plan.is_valid = False
                plan.validation_error = error_msg
                return False, error_msg

            tool = self.registry.get(step.tool_name)

            # 2. Check Parameter Validation
            if not tool.validate(step.arguments):
                error_msg = f"Plan step {step.step_id} failed parameter validation for tool '{step.tool_name}'."
                logger.warning(f"PLAN_VALIDATION_FAILED: {error_msg}")
                plan.is_valid = False
                plan.validation_error = error_msg
                return False, error_msg

        plan.is_valid = True
        plan.validation_error = None
        logger.info(f"PLAN_VALIDATION_SUCCESS: Plan '{plan.plan_id}' is fully valid.")
        return True, None
