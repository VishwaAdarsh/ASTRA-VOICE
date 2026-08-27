"""
Automation Validator Component.
Validates automation draft rules against system policies, rate limits, and safety boundaries.
"""

from src.core.config import Config
from src.core.exceptions import AutomationValidationError
from src.core.logger import get_logger
from src.automation.models import ActionType, Automation, AutomationDraft
from src.tools.registry import ToolRegistry

logger = get_logger()


class AutomationValidator:
    """Validates AutomationDraft and Automation instances against limits and security policies."""

    def __init__(self, config: Config | None = None, registry: ToolRegistry | None = None):
        self.config = config or Config()
        self.registry = registry or ToolRegistry()

    def validate_draft(self, draft: AutomationDraft, active_count: int = 0) -> bool:
        """Validate draft creation rules before persistence."""
        # 1. Total Active Count Limit
        max_active = self.config.max_active_automations
        if active_count >= max_active:
            raise AutomationValidationError(f"Maximum active automations limit reached ({active_count}/{max_active}).")

        # 2. Name validation
        if not draft.name or len(draft.name.strip()) < 3:
            raise AutomationValidationError("Automation name must be at least 3 characters long.")

        # 3. Action Tool allowlist validation
        action_type = draft.action_config.get("type")
        tool_name = draft.action_config.get("tool")

        if action_type != ActionType.NOTIFY.value and tool_name:
            if not self.registry.has_tool(tool_name):
                raise AutomationValidationError(f"Automation specifies unregistered tool '{tool_name}'.")

        logger.info(f"AutomationValidator successfully validated draft '{draft.name}'.")
        return True

    def validate_automation(self, auto: Automation) -> bool:
        """Validate an instantiated Automation rule."""
        if not auto.id or not auto.name:
            raise AutomationValidationError("Automation ID and name are required.")

        return True
