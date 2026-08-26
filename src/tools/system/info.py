"""
System Information Tool.
Queries OS architecture, platform name, and system information.
"""

import platform
import time
from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.tools.base import BaseTool


class SystemInformationTool(BaseTool):
    """Tool to query basic operating system information."""

    name = "system_information"
    description = "Queries operating system information, architecture, and platform details."
    permission_level = PermissionLevel.SAFE

    def validate(self, parameters: dict[str, Any]) -> bool:
        return isinstance(parameters, dict)

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        start_time = time.time()
        try:
            info = {
                "os": platform.system(),
                "os_release": platform.release(),
                "os_version": platform.version(),
                "architecture": platform.architecture()[0],
                "machine": platform.machine(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
            }

            msg = f"System: {info['os']} {info['os_release']} ({info['architecture']}), Machine: {info['machine']}."
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=msg,
                data=info,
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to query system information: {e}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
