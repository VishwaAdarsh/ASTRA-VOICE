"""
System Information Tool.
Collects non-sensitive OS, Python runtime, architecture, and hardware information.
"""

import platform
import socket
import sys
import time
from typing import Any
import psutil
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.logger import get_logger
from src.tools.base import BaseTool

logger = get_logger()


class SystemInformationTool(BaseTool):
    """Tool to collect safe system information."""

    name = "system_information"
    description = "Displays non-sensitive system specs, Python runtime, and resource usage."
    permission_level = PermissionLevel.SAFE

    def validate(self, parameters: dict[str, Any]) -> bool:
        return True

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        start_time = time.time()
        try:
            os_name = platform.system()
            os_release = platform.release()
            os_version = platform.version()
            python_version = sys.version.split()[0]
            architecture = platform.machine()
            hostname = socket.gethostname()

            # psutil memory information
            mem = psutil.virtual_memory()
            total_ram_gb = round(mem.total / (1024**3), 2)
            available_ram_gb = round(mem.available / (1024**3), 2)

            info_data = {
                "operating_system": f"{os_name} {os_release}",
                "os_version": os_version,
                "python_version": python_version,
                "architecture": architecture,
                "hostname": hostname,
                "total_memory_gb": total_ram_gb,
                "available_memory_gb": available_ram_gb,
            }

            # Build formatted display string for CLI output
            msg_lines = [
                f"Operating System: {os_name} {os_release} ({architecture})",
                f"Python Version: {python_version}",
                f"Hostname: {hostname}",
                f"RAM: {available_ram_gb} GB free of {total_ram_gb} GB total",
            ]
            summary_message = "\n".join(msg_lines)

            logger.info("Successfully gathered system information.")
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=summary_message,
                data=info_data,
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            logger.error(f"Failed to gather system information: {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message="Failed to retrieve system information.",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
