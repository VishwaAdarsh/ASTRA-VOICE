"""
Safe Delete File Tool.
Relocates deleted files into a safe trash location with CONFIRM permission policy to prevent unrecoverable deletion.
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


class DeleteFileTool(BaseTool):
    """Tool for safely deleting a file or folder by moving it to safe trash storage."""

    def __init__(self, config: Config | None = None, path_resolver: PathResolver | None = None):
        self.config = config or Config()
        self.resolver = path_resolver or PathResolver(config=self.config)
        self.trash_dir = self.config.root_dir / "data" / "trash"
        self.trash_dir.mkdir(parents=True, exist_ok=True)

    @property
    def name(self) -> str:
        return "delete_file"

    @property
    def description(self) -> str:
        return "Safely deletes a file or directory by moving it to safe trash storage."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.CONFIRM

    def validate(self, parameters: dict[str, Any]) -> bool:
        return "target" in parameters and isinstance(parameters["target"], str)

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        target_str = str(parameters["target"])

        try:
            target_path = self.resolver.resolve_file(target_str)
            if not target_path.exists():
                return ToolResult(
                    status=ExecutionStatus.NOT_FOUND,
                    message=f"Target '{target_str}' does not exist.",
                )

            # Move to safe trash directory rather than permanent unrecoverable unlink
            dest_trash = self.trash_dir / target_path.name
            if dest_trash.exists():
                if dest_trash.is_dir():
                    shutil.rmtree(str(dest_trash))
                else:
                    dest_trash.unlink()

            shutil.move(str(target_path), str(dest_trash))
            logger.info(f"Safely moved '{target_path}' to trash '{dest_trash}'")

            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=f"File '{target_path.name}' deleted (moved to safe trash).",
                data={"original_path": str(target_path), "trash_path": str(dest_trash)},
            )
        except Exception as e:
            logger.error(f"DeleteFileTool failed: {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to delete: {e}",
                error=str(e),
            )
