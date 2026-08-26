"""
Unit tests for ToolExecutor engine.
"""

from unittest.mock import MagicMock, patch
from src.brain.models import ExecutionStatus, PermissionLevel, ToolRequest, ToolResult
from src.core.config import Config
from src.execution.executor import ToolExecutor
from src.execution.verifier import ToolVerifier
from src.security.confirmation import AutoApproveConfirmationHandler
from src.security.permissions import PermissionManager
from src.tools.applications import OpenApplicationTool
from src.tools.base import BaseTool
from src.tools.registry import ToolRegistry


class FailingTool(BaseTool):
    name = "failing_tool"
    description = "A tool that throws an exception"
    permission_level = PermissionLevel.SAFE

    def validate(self, parameters: dict) -> bool:
        return True

    def execute(self, parameters: dict) -> ToolResult:
        raise RuntimeError("Simulated internal tool crash")


class ConfirmTool(BaseTool):
    name = "confirm_tool"
    description = "A tool requiring user confirmation"
    permission_level = PermissionLevel.CONFIRM

    def validate(self, parameters: dict) -> bool:
        return True

    def execute(self, parameters: dict) -> ToolResult:
        return ToolResult(status=ExecutionStatus.SUCCESS, message="Confirmed tool executed")


@patch("subprocess.Popen")
def test_executor_successful_execution(mock_popen):
    config = Config()
    registry = ToolRegistry()
    tool = OpenApplicationTool(config=config)
    registry.register(tool)

    pm = PermissionManager(config=config)
    verifier = ToolVerifier(config=config)
    executor = ToolExecutor(registry=registry, permission_manager=pm, verifier=verifier)

    request = ToolRequest(tool_name="open_application", parameters={"app_name": "calculator"})
    result = executor.execute(request)

    assert result.status == ExecutionStatus.SUCCESS
    assert "Calculator opened" in result.message


def test_executor_unregistered_tool():
    config = Config()
    registry = ToolRegistry()
    pm = PermissionManager(config=config)
    executor = ToolExecutor(registry=registry, permission_manager=pm)

    request = ToolRequest(tool_name="unknown_tool", parameters={})
    result = executor.execute(request)

    assert result.status == ExecutionStatus.NOT_FOUND


def test_executor_failing_tool_graceful_catch():
    registry = ToolRegistry()
    registry.register(FailingTool())
    config = Config()
    pm = PermissionManager(config=config)

    executor = ToolExecutor(registry=registry, permission_manager=pm)
    request = ToolRequest(tool_name="failing_tool", parameters={})
    result = executor.execute(request)

    assert result.status == ExecutionStatus.FAILED
    assert "I couldn't complete that action" in result.message
    assert "Simulated internal tool crash" in result.error


def test_executor_confirmation_handling():
    registry = ToolRegistry()
    registry.register(ConfirmTool())
    config = Config()
    pm = PermissionManager(config=config)

    # Approved handler
    approved_handler = AutoApproveConfirmationHandler(approve=True)
    executor_approved = ToolExecutor(
        registry=registry, permission_manager=pm, confirmation_handler=approved_handler
    )
    request = ToolRequest(tool_name="confirm_tool", parameters={})
    res1 = executor_approved.execute(request)
    assert res1.status == ExecutionStatus.SUCCESS

    # Denied handler
    denied_handler = AutoApproveConfirmationHandler(approve=False)
    executor_denied = ToolExecutor(
        registry=registry, permission_manager=pm, confirmation_handler=denied_handler
    )
    res2 = executor_denied.execute(request)
    assert res2.status == ExecutionStatus.DENIED
