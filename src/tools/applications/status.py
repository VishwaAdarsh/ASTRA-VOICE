"""
Application Status Inspection Tool.
Inspects whether an application process is running on Windows.
"""

import subprocess
from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.tools.applications.aliases import ApplicationRegistry
from src.tools.base import BaseTool


class ApplicationStatusTool(BaseTool):
    """Tool for checking if an application process is running."""

    def __init__(self, config: Config | None = None, app_registry: ApplicationRegistry | None = None):
        self.config = config or Config()
        self.app_registry = app_registry or ApplicationRegistry(config=self.config)

    @property
    def name(self) -> str:
        return "application_status"

    @property
    def description(self) -> str:
        return "Checks if a specific application (e.g. Chrome, Calculator, VS Code) is currently running."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.SAFE

    def validate(self, parameters: dict[str, Any]) -> bool:
        return "app_name" in parameters and isinstance(parameters["app_name"], str)

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        app_name = str(parameters["app_name"]).strip()
        exe_name = self.app_registry.resolve_executable(app_name) or app_name

        try:
            # Query tasklist on Windows
            output = subprocess.check_output(f'tasklist /FI "IMAGENAME eq {exe_name}"', shell=True, text=True)
            is_running = exe_name.lower() in output.lower()
            status_str = "RUNNING" if is_running else "NOT_RUNNING"

            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Application '{app_name}' status: {status_str}.",
                data={"app_name": app_name, "executable": exe_name, "status": status_str, "is_running": is_running},
            )
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to query application status: {e}",
                error=str(e),
            )
