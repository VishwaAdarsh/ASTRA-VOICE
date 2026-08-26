"""
Rename File Tool.
Renames files or folders with destination collision checks and CONFIRM permission policy.
"""

from pathlib import Path
from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.tools.base import BaseTool
from src.tools.filesystem.paths import PathResolver

logger = get_logger()


class RenameFileTool(BaseTool):
    """Tool to rename a file or directory."""

    def __init__(self, config: Config | None = None, path_resolver: PathResolver | None = None):
        self.config = config or Config()
        self.resolver = path_resolver or PathResolver(config=self.config)

    @property
    def name(self) -> str:
        return "rename_file"

    @property
    def description(self) -> str:
        return "Renames an existing file or directory."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.CONFIRM

    def validate(self, parameters: dict[str, Any]) -> bool:
        return (
            "source" in parameters
            and "new_name" in parameters
            and isinstance(parameters["source"], str)
            and isinstance(parameters["new_name"], str)
        )

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        source_str = str(parameters["source"])
        new_name = str(parameters["new_name"]).strip()

        try:
            source_path = self.resolver.resolve_file(source_str)
            if not source_path.exists():
                return ToolResult(
                    status=ExecutionStatus.NOT_FOUND,
                    message=f"Source file '{source_str}' does not exist.",
                )

            dest_path = source_path.parent / new_name
            self.resolver.validate_path_security(dest_path)

            if dest_path.exists():
                return ToolResult(
                    status=ExecutionStatus.DENIED,
                    message=f"Destination '{new_name}' already exists. Overwriting prevented.",
                )

            source_path.rename(dest_path)
            logger.info(f"Renamed '{source_path}' to '{dest_path}'")

            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Renamed '{source_path.name}' to '{new_name}'.",
                data={"old_path": str(source_path), "new_path": str(dest_path)},
            )
        except Exception as e:
            logger.error(f"RenameFileTool failed: {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to rename: {e}",
                error=str(e),
            )
