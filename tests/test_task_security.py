"""
Security and bounds tests for Task Engine.
"""

import pytest
from src.core.exceptions import PlanValidationError
from src.task.models import ActionRiskLevel, TaskPlan, TaskStep
from src.task.validator import PlanValidator
from src.tools.filesystem import SearchFilesTool
from src.tools.registry import ToolRegistry



def test_task_validator_step_limit_enforcement():
    registry = ToolRegistry()
    registry.register(SearchFilesTool())

    validator = PlanValidator(registry=registry)
    validator.config.agent_max_steps = 5

    # Create 6 steps plan
    steps = [
        TaskStep(step_number=i, description=f"Step {i}", tool_name="search_files", arguments={"query": "test"})
        for i in range(1, 7)
    ]
    plan = TaskPlan(goal="Excessive steps goal", steps=steps)

    with pytest.raises(PlanValidationError) as exc:
        validator.validate_plan(plan)
    assert "exceeds maximum step limit" in str(exc.value)


def test_task_validator_replan_limit_enforcement():
    registry = ToolRegistry()
    registry.register(SearchFilesTool())

    validator = PlanValidator(registry=registry)
    validator.config.agent_max_replans = 3

    step = TaskStep(step_number=1, description="Step 1", tool_name="search_files", arguments={"query": "test"})
    plan = TaskPlan(goal="Replan goal", steps=[step])

    with pytest.raises(PlanValidationError) as exc:
        validator.validate_plan(plan, current_replan_count=4)
    assert "exceeded maximum replanning limit" in str(exc.value)
