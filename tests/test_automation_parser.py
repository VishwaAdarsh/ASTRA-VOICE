"""
Unit tests for AutomationParser.
"""

from src.automation.models import ActionType, TriggerType
from src.automation.parser import AutomationParser


def test_automation_parser_reminder():
    parser = AutomationParser()
    draft = parser.parse_request("Remind me tomorrow at 8 PM to submit assignment")

    assert "Reminder" in draft.name
    assert draft.trigger_type == TriggerType.SCHEDULE
    assert draft.trigger_config.get("time") == "20:00"
    assert draft.action_config.get("type") == ActionType.NOTIFY.value


def test_automation_parser_condition_watch():
    parser = AutomationParser()
    draft = parser.parse_request("Tell me when a new report appears in downloads")

    assert "Condition Watch" in draft.name
    assert draft.trigger_type == TriggerType.CONDITION
    assert draft.condition_config is not None
