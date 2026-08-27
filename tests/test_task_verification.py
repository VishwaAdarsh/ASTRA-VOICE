"""
Unit tests for TaskVerifier.
"""

from src.brain.models import ExecutionStatus, ToolResult
from src.task.models import ActionRiskLevel, TaskStep
from src.task.verifier import TaskVerifier


def test_task_verifier_file_creation(tmp_path):
    verifier = TaskVerifier()
    test_file = tmp_path / "test_verify.txt"
    test_file.write_text("verification data")

    step = TaskStep(
        step_number=1,
        description="Create text file",
        tool_name="create_text_file",
        arguments={"file_path": str(test_file)},
    )
    tool_res = ToolResult(status=ExecutionStatus.SUCCESS, message="File created")

    res = verifier.verify_step(step, tool_res)
    assert res.success == True
    assert "FILE_SYSTEM_EXISTS" in res.method


def test_task_verifier_failed_execution():
    verifier = TaskVerifier()
    step = TaskStep(step_number=1, description="System info", tool_name="system_info")
    tool_res = ToolResult(status=ExecutionStatus.FAILED, message="System error", error="System error")

    res = verifier.verify_step(step, tool_res)
    assert res.success == False
    assert res.method == "STATUS_CHECK"

