"""
Unit tests for Applications and Projects Subsystem tools (Phase 5).
"""

from unittest.mock import patch
from src.brain.models import ExecutionStatus, PermissionLevel
from src.core.config import Config
from src.tools.applications.aliases import ApplicationRegistry
from src.tools.applications.lifecycle import CloseApplicationTool
from src.tools.applications.projects import OpenProjectTool, ProjectRegistry
from src.tools.applications.status import ApplicationStatusTool


def test_application_alias_resolution():
    reg = ApplicationRegistry()
    assert reg.resolve_executable("code") == "code"
    assert reg.resolve_executable("vscode") == "code"
    assert reg.resolve_executable("calculator") == "calc.exe"


def test_application_status_tool():
    tool = ApplicationStatusTool()
    res = tool.execute({"app_name": "calculator"})
    assert res.status == ExecutionStatus.SUCCESS
    assert "status" in res.data


@patch("subprocess.run")
def test_close_application_tool(mock_run):
    tool = CloseApplicationTool()

    # Permission level check
    assert tool.permission_level == PermissionLevel.CONFIRM

    res = tool.execute({"app_name": "calculator"})
    assert res.status == ExecutionStatus.SUCCESS
    mock_run.assert_called_once()


def test_open_project_tool(tmp_path):
    config = Config()
    config.project_dirs = [tmp_path]

    # Create dummy project directory
    proj_dir = tmp_path / "ASTRA-VOICE"
    proj_dir.mkdir()

    tool = OpenProjectTool(config=config)
    res = tool.execute({"project_name": "ASTRA-VOICE"})

    assert res.status == ExecutionStatus.SUCCESS
    assert res.data["project_name"] == "ASTRA-VOICE"
