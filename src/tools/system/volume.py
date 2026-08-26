"""
Volume Control Tool.
Controls system audio volume (volume up, volume down, mute) on Windows.
"""

from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.logger import get_logger
from src.tools.base import BaseTool

logger = get_logger()


class VolumeControlTool(BaseTool):
    """Tool to adjust or mute audio output volume."""

    @property
    def name(self) -> str:
        return "volume_control"

    @property
    def description(self) -> str:
        return "Adjusts system audio output volume (action: 'up', 'down', 'mute')."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.SAFE

    def validate(self, parameters: dict[str, Any]) -> bool:
        return "action" in parameters and isinstance(parameters["action"], str)

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        action = str(parameters["action"]).lower().strip()

        if action not in ("up", "down", "mute", "unmute"):
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Invalid volume action '{action}'. Supported: 'up', 'down', 'mute'.",
            )

        try:
            # On Windows, trigger volume media keys via vbs/powershell
            import subprocess
            if action == "up":
                key_code = "{VK_VOLUME_UP 5}"
            elif action == "down":
                key_code = "{VK_VOLUME_DOWN 5}"
            else:
                key_code = "{VK_VOLUME_MUTE}"

            cmd = f'powershell -c "$wshell = New-Object -ComObject wscript.shell; $wshell.SendKeys(\'{key_code}\')"'
            subprocess.run(cmd, shell=True, check=False)

            logger.info(f"Volume action '{action}' executed.")
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Volume action '{action}' completed.",
                data={"action": action},
            )
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to execute volume action: {e}",
                error=str(e),
            )
