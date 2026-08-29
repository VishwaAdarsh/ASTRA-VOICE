"""
Open File and Open Folder Tools.
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
from src.tools.filesystem.paths import PathResolver

logger = get_logger()


class OpenFileTool(BaseTool):
    """Tool to open a file in Windows default application."""

    def __init__(self, config: Config | None = None, path_resolver: PathResolver | None = None):
        self.config = config or Config()
        self.resolver = path_resolver or PathResolver(config=self.config)

    @property
    def name(self) -> str:
        return "open_file"

    @property
    def description(self) -> str:
        return "Opens a target file using Windows default associated application."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.SAFE

    parameters_schema = {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Path or filename of target file to open with default application",
            }
        },
        "required": ["target"],
    }

    def validate(self, parameters: dict[str, Any]) -> bool:
        return "target" in parameters and isinstance(parameters["target"], str)

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        target_str = str(parameters["target"])
        try:
            file_path = self.resolver.resolve_file(target_str)
            if not file_path.exists():
                return ToolResult(
                    status=ExecutionStatus.NOT_FOUND,
                    message=f"File '{target_str}' does not exist.",
                )

            logger.info(f"Opening file '{file_path}'")
            if hasattr(os, "startfile"):
                os.startfile(str(file_path))
            else:
                subprocess.Popen(["cmd.exe", "/c", "start", "", str(file_path)])

            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Opened file '{file_path.name}'.",
                data={"path": str(file_path)},
            )
        except Exception as e:
            logger.error(f"OpenFileTool failed: {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to open file: {e}",
                error=str(e),
            )


class OpenFolderTool(BaseTool):
    """Tool to open allowlisted system folders on Windows."""

    name = "open_folder"
    description = "Opens a safe allowlisted folder in Windows File Explorer."
    permission_level = PermissionLevel.SAFE

    parameters_schema = {
        "type": "object",
        "properties": {
            "folder_name": {
                "type": "string",
                "description": "Folder name (e.g. 'downloads', 'documents', 'desktop', 'pictures', 'videos', 'music', 'home') or directory path to open",
            }
        },
        "required": ["folder_name"],
    }

    def __init__(self, config: Config | None = None, path_resolver: PathResolver | None = None):
        self.config = config or Config()
        self.resolver = path_resolver or PathResolver(config=self.config)

    def validate(self, parameters: dict[str, Any]) -> bool:
        folder_name = parameters.get("folder_name")
        if not folder_name or not isinstance(folder_name, str):
            return False
        return self.config.get_folder_path(folder_name) is not None or self.config.is_app_allowed(folder_name)



    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        start_time = time.time()
        folder_name = parameters.get("folder_name", "").strip()

        try:
            folder_path = self.resolver.resolve_folder(folder_name)
            if not folder_path.exists():
                return ToolResult(
                    status=ExecutionStatus.NOT_FOUND,
                    message=f"Folder '{folder_name}' does not exist.",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            if hasattr(os, "startfile"):
                os.startfile(str(folder_path))
            else:
                subprocess.Popen(["explorer.exe", str(folder_path)])

            formatted_name = folder_name.capitalize()
            logger.info(f"Successfully opened folder '{folder_path}' ({folder_name})")

            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=f"{formatted_name} opened.",
                data={"folder_name": folder_name, "path": str(folder_path)},
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
