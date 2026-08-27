"""
Unit tests for TaskPlanner and PlanValidator.
"""

import pytest
from src.core.exceptions import PlanValidationError
from src.task.models import ActionRiskLevel, TaskPlan, TaskStep
from src.task.planner import TaskPlanner
from src.task.validator import PlanValidator
from src.tools.filesystem import CreateTextFileTool, FileMetadataTool, OpenFileTool, SearchFilesTool
from src.tools.registry import ToolRegistry



def test_task_planner_generate_plan():
    planner = TaskPlanner()
    plan = planner.generate_plan("Find my project report and summarize it")

    assert plan.goal == "Find my project report and summarize it"
    assert len(plan.steps) >= 3
    assert plan.steps[0].tool_name == "search_files"
    assert plan.steps[1].tool_name == "open_file"


def test_plan_validator():
    registry = ToolRegistry()
    registry.register(SearchFilesTool())
    registry.register(OpenFileTool())
    registry.register(CreateTextFileTool())
    registry.register(FileMetadataTool())

    validator = PlanValidator(registry=registry)
    planner = TaskPlanner()

    plan = planner.generate_plan("Find my project report and summarize it")
    assert validator.validate_plan(plan) == True


def test_plan_validator_unregistered_tool():
    registry = ToolRegistry()
    validator = PlanValidator(registry=registry)

    invalid_step = TaskStep(step_number=1, description="Bad tool step", tool_name="unregistered_tool", arguments={})
    invalid_plan = TaskPlan(goal="Test goal", steps=[invalid_step])

    with pytest.raises(PlanValidationError) as exc:
        validator.validate_plan(invalid_plan)
    assert "unregistered tool" in str(exc.value)
