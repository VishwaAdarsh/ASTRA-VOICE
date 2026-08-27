"""
Security and bounds tests for Proactive Automation Engine.
"""

import pytest
from src.core.config import Config
from src.core.exceptions import AutomationValidationError
from src.automation.models import ActionType, AutomationDraft, TriggerType
from src.automation.validator import AutomationValidator
from src.tools.registry import ToolRegistry


def test_automation_validator_max_active_limit():
    cfg = Config()
    cfg.max_active_automations = 2
    validator = AutomationValidator(config=cfg)

    draft = AutomationDraft(
        name="Test Automation",
        trigger_type=TriggerType.SCHEDULE,
        trigger_config={"time": "09:00"},
        action_config={"type": ActionType.NOTIFY.value},
    )

    with pytest.raises(AutomationValidationError) as exc:
        validator.validate_draft(draft, active_count=2)
    assert "Maximum active automations limit reached" in str(exc.value)


def test_automation_validator_unregistered_tool():
    registry = ToolRegistry()
    validator = AutomationValidator(registry=registry)

    draft = AutomationDraft(
        name="Bad Tool Automation",
        trigger_type=TriggerType.SCHEDULE,
        trigger_config={"time": "09:00"},
        action_config={"type": ActionType.RUN_APPROVED_TASK.value, "tool": "unregistered_tool"},
    )

    with pytest.raises(AutomationValidationError) as exc:
        validator.validate_draft(draft, active_count=0)
    assert "unregistered tool" in str(exc.value)
