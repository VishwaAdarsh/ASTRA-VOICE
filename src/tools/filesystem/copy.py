"""
Copy File Tool.
Copies files or folders to a target destination directory with CONFIRM permission policy.
"""

import shutil
from pathlib import Path
from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.tools.base import BaseTool
from src.tools.filesystem.paths import PathResolver

logger = get_logger()


class CopyFileTool(BaseTool):
    """Tool to copy a file or folder."""

    def __init__(self, config: Config | None = None, path_resolver: PathResolver | None = None):
        self.config = config or Config()
        self.resolver = path_resolver or PathResolver(config=self.config)

    @property
    def name(self) -> str:
        return "copy_file"

    @property
    def description(self) -> str:
        return "Copies a file or folder to a target destination directory."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.CONFIRM

    def validate(self, parameters: dict[str, Any]) -> bool:
        return (
            "source" in parameters
            and "destination" in parameters
            and isinstance(parameters["source"], str)
            and isinstance(parameters["destination"], str)
        )

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        source_str = str(parameters["source"])
        dest_str = str(parameters["destination"])

        try:
            source_path = self.resolver.resolve_file(source_str)
            if not source_path.exists():
                return ToolResult(
                    status=ExecutionStatus.NOT_FOUND,
                    message=f"Source '{source_str}' does not exist.",
                )

            dest_folder = self.resolver.resolve_folder(dest_str)
            dest_path = dest_folder / source_path.name
            self.resolver.validate_path_security(dest_path)

            if dest_path.exists():
                return ToolResult(
                    status=ExecutionStatus.DENIED,
                    message=f"Destination '{dest_path.name}' already exists. Overwriting prevented.",
                )

            if source_path.is_dir():
                shutil.copytree(str(source_path), str(dest_path))
            else:
                shutil.copy2(str(source_path), str(dest_path))

            logger.info(f"Copied '{source_path}' to '{dest_path}'")

            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Copied '{source_path.name}' to '{dest_folder.name}'.",
                data={"source": str(source_path), "destination": str(dest_path)},
            )
        except Exception as e:
            logger.error(f"CopyFileTool failed: {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to copy: {e}",
                error=str(e),
            )
