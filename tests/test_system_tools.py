"""
Unit tests for System Subsystem tools (Phase 5).
"""

from unittest.mock import patch
from src.brain.models import ExecutionStatus
from src.core.config import Config
from src.tools.system.resources import ResourceInformationTool
from src.tools.system.screenshot import ScreenshotTool
from src.tools.system.volume import VolumeControlTool


def test_resource_information_tool():
    tool = ResourceInformationTool()
    res = tool.execute({})
    assert res.status == ExecutionStatus.SUCCESS
    assert "disk" in res.data
    assert "cpu_cores" in res.data


def test_screenshot_tool(tmp_path):
    config = Config()
    config.screenshots_dir = tmp_path

    tool = ScreenshotTool(config=config)
    res = tool.execute({})

    assert res.status == ExecutionStatus.SUCCESS
    assert "filename" in res.data
    assert (tmp_path / res.data["filename"]).exists()


@patch("subprocess.run")
def test_volume_control_tool(mock_run):
    tool = VolumeControlTool()
    res = tool.execute({"action": "up"})
    assert res.status == ExecutionStatus.SUCCESS
    mock_run.assert_called_once()
