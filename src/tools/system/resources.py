"""
System Resource Information Tool.
Provides read-only memory, CPU, disk, and system resource metrics.
"""

import os
import platform
import shutil
from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.tools.base import BaseTool


class ResourceInformationTool(BaseTool):
    """Tool to query system hardware resource utilization."""

    @property
    def name(self) -> str:
        return "resource_information"

    @property
    def description(self) -> str:
        return "Queries CPU, RAM, disk usage, and hardware resource stats."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.SAFE

    def validate(self, parameters: dict[str, Any]) -> bool:
        return isinstance(parameters, dict)

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        try:
            # Disk Usage
            total, used, free = shutil.disk_usage("/")
            disk_gb = {
                "total_gb": round(total / (1024**3), 2),
                "used_gb": round(used / (1024**3), 2),
                "free_gb": round(free / (1024**3), 2),
                "percent_used": round((used / total) * 100, 1),
            }

            # System Metrics
            cpu_count = os.cpu_count() or 1
            os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"

            msg = f"System Stats ({os_info}): Disk Free: {disk_gb['free_gb']} GB / {disk_gb['total_gb']} GB ({disk_gb['percent_used']}% used), CPU Cores: {cpu_count}."

            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=msg,
                data={
                    "os": os_info,
                    "cpu_cores": cpu_count,
                    "disk": disk_gb,
                },
            )
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to query resource stats: {e}",
                error=str(e),
            )
