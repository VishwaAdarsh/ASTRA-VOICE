"""
Unit tests for TaskPlanner and PlanValidator.
"""

from src.brain.llm.models import DecisionType, LLMDecision
from src.brain.planning.planner import TaskPlanner
from src.brain.planning.validator import PlanValidator
from src.core.config import Config
from src.security.permissions import PermissionManager
from src.tools.applications import OpenApplicationTool
from src.tools.registry import ToolRegistry


def test_planner_and_validator_valid_plan():
    config = Config()
    registry = ToolRegistry()
    registry.register(OpenApplicationTool(config=config))

    pm = PermissionManager(config=config)
    planner = TaskPlanner()
    validator = PlanValidator(registry=registry, permission_manager=pm)

    decision = LLMDecision(
        decision_type=DecisionType.PLAN,
        steps=[{"tool": "open_application", "arguments": {"app_name": "calculator"}}],
    )

    plan = planner.create_plan_from_decision(decision, "Open calc")
    is_valid, err = validator.validate(plan)

    assert is_valid is True
    assert err is None


def test_planner_and_validator_unregistered_tool():
    config = Config()
    registry = ToolRegistry()
    pm = PermissionManager(config=config)
    planner = TaskPlanner()
    validator = PlanValidator(registry=registry, permission_manager=pm)

    decision = LLMDecision(
        decision_type=DecisionType.PLAN,
        steps=[{"tool": "unregistered_malicious_tool", "arguments": {}}],
    )

    plan = planner.create_plan_from_decision(decision, "Malicious request")
    is_valid, err = validator.validate(plan)

    assert is_valid is False
    assert "unregistered tool" in err
