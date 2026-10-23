"""
Application Status Inspection Tool.
Inspects whether an application process is running on Windows safely without shell execution.
"""

import os
from pathlib import Path
import subprocess
from typing import Any
import psutil

from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.tools.applications.aliases import ApplicationRegistry
from src.tools.base import BaseTool

logger = get_logger()


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
        return "Checks if a specific application (e.g. Chrome, Calculator, VS Code, Notepad) is currently running."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.SAFE

    def validate(self, parameters: dict[str, Any]) -> bool:
        return "app_name" in parameters and isinstance(parameters["app_name"], str)

    def _get_candidate_names(self, app_name: str, exe_name: str) -> set[str]:
        """Derive set of candidate process image names (lowercased)."""
        candidates = set()
        clean_app = app_name.lower().strip()
        clean_exe = Path(exe_name).name.lower().strip()

        candidates.add(clean_exe)
        if clean_exe.endswith(".exe"):
            candidates.add(clean_exe[:-4])
        else:
            candidates.add(f"{clean_exe}.exe")

        candidates.add(clean_app)
        if not clean_app.endswith(".exe"):
            candidates.add(f"{clean_app}.exe")

        # Handle known Windows 10/11 system app aliases
        if clean_app in ("calc", "calculator", "calc.exe"):
            candidates.update({"calc.exe", "calculator.exe", "calculatorapp.exe"})
        elif clean_app in ("code", "vscode", "visual studio code"):
            candidates.update({"code.exe", "code"})
        elif clean_app in ("notepad", "notepad.exe"):
            candidates.update({"notepad.exe", "notepad"})
        elif clean_app in ("paint", "mspaint", "mspaint.exe"):
            candidates.update({"mspaint.exe", "paint.exe"})
        elif clean_app in ("edge", "msedge", "microsoft edge"):
            candidates.update({"msedge.exe"})
        elif clean_app in ("chrome", "google chrome"):
            candidates.update({"chrome.exe"})

        return candidates

    def is_process_running(self, app_name: str, exe_name: str) -> tuple[bool, int | None]:
        """Check if application process is running using psutil with safe non-shell fallback."""
        candidates = self._get_candidate_names(app_name, exe_name)

        # 1. Primary inspection via psutil (safe, direct process table iteration)
        psutil_succeeded = False
        try:
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    pname = (proc.info.get("name") or "").lower()
                    if pname in candidates:
                        return True, proc.info.get("pid")
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            psutil_succeeded = True
        except Exception as e:
            logger.debug(f"psutil process iteration encountered: {e}")

        # 2. Safe non-shell fallback via tasklist on Windows only if psutil was unavailable
        if not psutil_succeeded and os.name == "nt":
            for target_name in candidates:
                if not target_name.endswith(".exe"):
                    target_name = f"{target_name}.exe"
                try:
                    res = subprocess.run(
                        ["tasklist", "/FI", f"IMAGENAME eq {target_name}"],
                        capture_output=True,
                        text=True,
                        shell=False,
                        timeout=2.0,
                    )
                    if res.returncode == 0 and target_name.lower() in res.stdout.lower():
                        return True, None
                except Exception:
                    continue

        return False, None

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        app_name = str(parameters["app_name"]).strip()
        exe_name = self.app_registry.resolve_executable(app_name) or app_name

        try:
            is_running, pid = self.is_process_running(app_name, exe_name)
            status_str = "RUNNING" if is_running else "NOT_RUNNING"

            formatted_name = app_name.capitalize()
            if is_running:
                message = f"{formatted_name} is currently running."
            else:
                message = f"{formatted_name} is not running."

            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=message,
                data={
                    "app_name": app_name,
                    "executable": exe_name,
                    "status": status_str,
                    "is_running": is_running,
                    "pid": pid,
                },
            )
        except Exception as e:
            logger.error(f"Failed to query application status for '{app_name}': {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to query application status: {e}",
                error=str(e),
            )
