"""
Open Application Tool.
Launches allowlisted desktop applications on Windows with pre-launch validation and launch verification.
"""

import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.tools.applications.aliases import ApplicationRegistry
from src.tools.applications.status import ApplicationStatusTool
from src.tools.base import BaseTool

logger = get_logger()


class OpenApplicationTool(BaseTool):
    """Tool to launch allowlisted desktop applications."""

    name = "open_application"
    description = "Launches an allowlisted Windows application."
    permission_level = PermissionLevel.SAFE

    parameters_schema = {
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "Name of application to launch (e.g. 'calculator', 'notepad', 'chrome', 'browser', 'vscode', 'settings', 'paint', 'cmd')",
            },
            "check_already_running": {
                "type": "boolean",
                "description": "If true and the application is already running, returns status without launching a duplicate instance.",
            },
        },
        "required": ["app_name"],
    }

    def __init__(
        self,
        config: Config | None = None,
        app_registry: ApplicationRegistry | None = None,
        status_tool: ApplicationStatusTool | None = None,
    ):
        self.config = config or Config()
        self.app_registry = app_registry or ApplicationRegistry(config=self.config)
        self.status_tool = status_tool or ApplicationStatusTool(config=self.config, app_registry=self.app_registry)

    def validate(self, parameters: dict[str, Any]) -> bool:
        app_name = parameters.get("app_name")
        if not app_name or not isinstance(app_name, str):
            return False
        return self.config.is_app_allowed(app_name) or self.app_registry.resolve_executable(app_name) is not None

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        start_time = time.time()
        app_name = parameters.get("app_name", "").strip()
        check_already_running = bool(parameters.get("check_already_running", False))

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

        formatted_name = app_name.capitalize()

        # Check if process is already running when requested
        is_already_running = False
        existing_pid = None
        if check_already_running:
            is_already_running, existing_pid = self.status_tool.is_process_running(app_name, executable)
            if is_already_running:
                logger.info(f"Application '{app_name}' is already running (PID={existing_pid})")
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    message=f"{formatted_name} is already running.",
                    data={
                        "app_name": app_name,
                        "executable": executable,
                        "is_already_running": True,
                        "launched": False,
                        "pid": existing_pid,
                    },
                    execution_time_ms=(time.time() - start_time) * 1000,
                    verified=True,
                )

        try:
            proc = None
            # Special case: Windows Settings URI scheme
            if executable.startswith("ms-settings:"):
                if hasattr(os, "startfile"):
                    os.startfile(executable)
                else:
                    subprocess.Popen(
                        ["cmd.exe", "/c", "start", executable],
                        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                    )
                launched_pid = None
            else:
                # Verify that non-URI binary exists on disk or PATH
                if not os.path.exists(executable) and not shutil.which(executable):
                    # Try appending .exe if missing
                    resolved_which = None
                    if not any(executable.lower().endswith(ext) for ext in (".exe", ".cmd", ".bat")):
                        resolved_which = shutil.which(f"{executable}.exe")
                    if resolved_which:
                        executable = resolved_which
                    else:
                        logger.warning(f"Executable '{executable}' for '{app_name}' not found on disk or PATH.")
                        return ToolResult(
                            status=ExecutionStatus.NOT_FOUND,
                            message=f"Application '{app_name}' is not installed or executable not found.",
                            error=f"Executable '{executable}' not found on disk or PATH.",
                            execution_time_ms=(time.time() - start_time) * 1000,
                        )

                # Use subprocess.Popen with safe argument list, shell=False
                creation_flags = 0
                if hasattr(subprocess, "DETACHED_PROCESS"):
                    creation_flags |= subprocess.DETACHED_PROCESS

                try:
                    proc = subprocess.Popen([executable], creationflags=creation_flags)
                except (FileNotFoundError, OSError) as e:
                    # Fallback on Windows: os.startfile via Shell execution
                    if hasattr(os, "startfile") and not isinstance(e, FileNotFoundError):
                        try:
                            os.startfile(executable)
                        except FileNotFoundError:
                            raise
                    else:
                        raise

                # Launch evidence verification: check if process died immediately with an error
                if proc and hasattr(proc, "poll"):
                    poll_res = proc.poll()
                    if isinstance(poll_res, int) and poll_res != 0:
                        logger.error(f"Process for '{app_name}' exited immediately with code {poll_res}")
                        return ToolResult(
                            status=ExecutionStatus.FAILED,
                            message=f"Failed to open '{app_name}'. Process exited with code {poll_res}.",
                            error=f"Process exited immediately with code {poll_res}",
                            execution_time_ms=(time.time() - start_time) * 1000,
                        )
                launched_pid = getattr(proc, "pid", existing_pid)

            logger.info(f"Successfully launched application '{executable}' ({app_name}) PID={launched_pid}")

            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=f"{formatted_name} opened.",
                data={
                    "app_name": app_name,
                    "executable": executable,
                    "is_already_running": is_already_running,
                    "launched": True,
                    "pid": launched_pid,
                },
                execution_time_ms=(time.time() - start_time) * 1000,
                verified=True,
            )
        except FileNotFoundError as fnfe:
            logger.error(f"Application executable not found for '{app_name}': {fnfe}")
            return ToolResult(
                status=ExecutionStatus.NOT_FOUND,
                message=f"Application '{app_name}' is not installed or executable not found.",
                error=str(fnfe),
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
