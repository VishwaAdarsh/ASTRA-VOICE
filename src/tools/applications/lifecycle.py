"""
Close Application Lifecycle Tool.
Gracefully closes approved running applications with CONFIRM permission policy.
"""

import subprocess
from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.tools.applications.aliases import ApplicationRegistry
from src.tools.base import BaseTool

logger = get_logger()


class CloseApplicationTool(BaseTool):
    """Tool to gracefully close a running application."""

    def __init__(self, config: Config | None = None, app_registry: ApplicationRegistry | None = None):
        self.config = config or Config()
        self.app_registry = app_registry or ApplicationRegistry(config=self.config)

    @property
    def name(self) -> str:
        return "close_application"

    @property
    def description(self) -> str:
        return "Gracefully closes a running application (e.g. Calculator, Notepad)."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.CONFIRM

    def validate(self, parameters: dict[str, Any]) -> bool:
        return "app_name" in parameters and isinstance(parameters["app_name"], str)

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        app_name = str(parameters["app_name"]).strip()
        exe_name = self.app_registry.resolve_executable(app_name)

        if not exe_name:
            return ToolResult(
                status=ExecutionStatus.NOT_FOUND,
                message=f"Application '{app_name}' is not in approved registry.",
            )

        try:
            logger.info(f"Attempting to close application '{app_name}' (exe='{exe_name}')")
            # Graceful process termination via taskkill on Windows
            cmd = f'taskkill /IM "{exe_name}" /T'
            subprocess.run(cmd, shell=True, check=False)

            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Closed application '{app_name}'.",
                data={"app_name": app_name, "executable": exe_name},
            )
        except Exception as e:
            logger.error(f"CloseApplicationTool failed: {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to close application: {e}",
                error=str(e),
            )
