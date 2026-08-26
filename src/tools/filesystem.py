"""
Open Folder Tool.
Opens common safe folders (Downloads, Documents, Desktop, Pictures) on Windows.
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.tools.base import BaseTool

logger = get_logger()


class OpenFolderTool(BaseTool):
    """Tool to open safe system folders in Windows File Explorer."""

    name = "open_folder"
    description = "Opens safe system folders (Downloads, Documents, Desktop, Pictures)."
    permission_level = PermissionLevel.SAFE

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def validate(self, parameters: dict[str, Any]) -> bool:
        folder_name = parameters.get("folder_name")
        if not folder_name or not isinstance(folder_name, str):
            return False
        path = self.config.get_folder_path(folder_name)
        return path is not None and path.exists()

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        start_time = time.time()
        folder_name = parameters.get("folder_name", "").strip()

        path = self.config.get_folder_path(folder_name)
        if not path:
            return ToolResult(
                status=ExecutionStatus.INVALID_REQUEST,
                message=f"Folder '{folder_name}' is not an authorized safe target.",
                error=f"Unallowed folder: {folder_name}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        if not path.exists():
            return ToolResult(
                status=ExecutionStatus.NOT_FOUND,
                message=f"That folder could not be found.",
                error=f"Path does not exist: {path}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            if hasattr(os, "startfile"):
                os.startfile(str(path))
            else:
                subprocess.Popen(["explorer.exe", str(path)])

            formatted_name = folder_name.capitalize()
            logger.info(f"Successfully opened folder '{path}'")

            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=f"{formatted_name} opened.",
                data={"folder_name": folder_name, "path": str(path)},
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            logger.error(f"Failed to open folder '{folder_name}': {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to open folder '{folder_name}'.",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
