"""
Unit tests for ToolRegistry and Tool Implementations.
"""

from unittest.mock import MagicMock, patch
import pytest
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.exceptions import ToolError, ToolNotFoundError
from src.tools.applications import OpenApplicationTool
from src.tools.base import BaseTool
from src.tools.browser import OpenWebsiteTool
from src.tools.filesystem import OpenFolderTool
from src.tools.registry import ToolRegistry
from src.tools.system import SystemInformationTool


class DummyTool(BaseTool):
    name = "dummy_tool"
    description = "Dummy test tool"
    permission_level = PermissionLevel.SAFE

    def validate(self, parameters: dict) -> bool:
        return True

    def execute(self, parameters: dict) -> ToolResult:
        return ToolResult(status=ExecutionStatus.SUCCESS, message="Dummy executed")


def test_registry_register_and_get():
    registry = ToolRegistry()
    dummy = DummyTool()
    registry.register(dummy)

    assert registry.contains("dummy_tool")
    retrieved = registry.get("dummy_tool")
    assert retrieved == dummy
    assert "dummy_tool" in registry.list_tools()


def test_registry_unknown_tool():
    registry = ToolRegistry()
    with pytest.raises(ToolNotFoundError):
        registry.get("nonexistent_tool")


def test_registry_invalid_tool_registration():
    registry = ToolRegistry()
    with pytest.raises(ToolError):
        registry.register("not_a_tool")  # type: ignore


@patch("subprocess.Popen")
def test_open_application_tool_success(mock_popen):
    config = Config()
    tool = OpenApplicationTool(config=config)

    assert tool.validate({"app_name": "calculator"})
    result = tool.execute({"app_name": "calculator"})

    assert result.status == ExecutionStatus.SUCCESS
    assert "Calculator opened" in result.message
    mock_popen.assert_called_once()


def test_open_application_tool_unallowed():
    config = Config()
    tool = OpenApplicationTool(config=config)

    assert not tool.validate({"app_name": "malicious.exe"})
    result = tool.execute({"app_name": "malicious.exe"})

    assert result.status == ExecutionStatus.INVALID_REQUEST


@patch("os.startfile", create=True)
@patch("subprocess.Popen")
def test_open_folder_tool_success(mock_popen, mock_startfile):
    config = Config()
    tool = OpenFolderTool(config=config)

    # Downloads folder should exist for user profile
    assert tool.validate({"folder_name": "downloads"})
    result = tool.execute({"folder_name": "downloads"})

    assert result.status == ExecutionStatus.SUCCESS
    assert "Downloads opened" in result.message


def test_open_folder_tool_unallowed():
    config = Config()
    tool = OpenFolderTool(config=config)

    result = tool.execute({"folder_name": "unauthorized_secret_dir"})
    assert result.status in (ExecutionStatus.NOT_FOUND, ExecutionStatus.INVALID_REQUEST, ExecutionStatus.FAILED)


@patch("webbrowser.open")
def test_open_website_tool_success(mock_webopen):
    config = Config()
    tool = OpenWebsiteTool(config=config)

    assert tool.validate({"target": "youtube"})
    result = tool.execute({"target": "youtube"})

    assert result.status == ExecutionStatus.SUCCESS
    assert "Youtube opened" in result.message
    mock_webopen.assert_called_once_with("https://www.youtube.com")


def test_system_information_tool():
    tool = SystemInformationTool()
    assert tool.validate({})

    result = tool.execute({})
    assert result.status == ExecutionStatus.SUCCESS
    assert "System:" in result.message or "Windows" in result.message
    assert "python_version" in result.data

