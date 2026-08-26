"""
Open Application Tool.
Launches allowlisted desktop applications on Windows.
"""

import subprocess
import time
from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.tools.applications.aliases import ApplicationRegistry
from src.tools.base import BaseTool

logger = get_logger()


class OpenApplicationTool(BaseTool):
    """Tool to launch allowlisted desktop applications."""

    name = "open_application"
    description = "Launches an allowlisted Windows application."
    permission_level = PermissionLevel.SAFE

    def __init__(self, config: Config | None = None, app_registry: ApplicationRegistry | None = None):
        self.config = config or Config()
        self.app_registry = app_registry or ApplicationRegistry(config=self.config)

    def validate(self, parameters: dict[str, Any]) -> bool:
        app_name = parameters.get("app_name")
        if not app_name or not isinstance(app_name, str):
            return False
        return self.config.is_app_allowed(app_name) or self.app_registry.resolve_executable(app_name) is not None

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        start_time = time.time()
        app_name = parameters.get("app_name", "").strip()

        if not self.validate(parameters):
            return ToolResult(
                status=ExecutionStatus.INVALID_REQUEST,
                message=f"Application '{app_name}' is not in the allowlist.",
                error=f"Unallowed application: {app_name}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        executable = self.app_registry.resolve_executable(app_name) or self.config.get_app_executable(app_name)
        if not executable:
            return ToolResult(
                status=ExecutionStatus.NOT_FOUND,
                message=f"Could not find application mapping for '{app_name}'.",
                error=f"Mapping missing for app {app_name}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            # Use subprocess.Popen with safe argument list, no shell=True
            subprocess.Popen([executable], creationflags=subprocess.DETACHED_PROCESS if hasattr(subprocess, "DETACHED_PROCESS") else 0)
            formatted_name = app_name.capitalize()
            logger.info(f"Successfully launched application '{executable}' ({app_name})")

            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=f"{formatted_name} opened.",
                data={"app_name": app_name, "executable": executable},
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            logger.error(f"Failed to launch application '{app_name}': {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to open '{app_name}'.",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
