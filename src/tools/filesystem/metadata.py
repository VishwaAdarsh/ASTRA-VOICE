"""
File Metadata Tool.
Retrieves metadata (size, timestamps, extension, parent) for a target file.
"""

from pathlib import Path
from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.tools.base import BaseTool
from src.tools.filesystem.paths import PathResolver


class FileMetadataTool(BaseTool):
    """Tool for reading metadata of a file or folder."""

    def __init__(self, config: Config | None = None, path_resolver: PathResolver | None = None):
        self.config = config or Config()
        self.resolver = path_resolver or PathResolver(config=self.config)

    @property
    def name(self) -> str:
        return "file_metadata"

    @property
    def description(self) -> str:
        return "Retrieves metadata (size, modification time, type) for a file."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.SAFE

    def validate(self, parameters: dict[str, Any]) -> bool:
        return "target" in parameters and isinstance(parameters["target"], str)

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        target_str = str(parameters["target"])
        location_str = parameters.get("location")
        try:
            base_folder = self.resolver.resolve_folder(location_str) if location_str else None
            target_path = self.resolver.resolve_file(target_str, base_folder=base_folder)
            if not target_path.exists():

                return ToolResult(
                    status=ExecutionStatus.NOT_FOUND,
                    message=f"File '{target_str}' does not exist.",
                )

            stat = target_path.stat()
            metadata = {
                "name": target_path.name,
                "path": str(target_path),
                "extension": target_path.suffix,
                "size_bytes": stat.st_size,
                "modified_time": stat.st_mtime,
                "created_time": stat.st_ctime,
                "is_directory": target_path.is_dir(),
            }

            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Retrieved metadata for '{target_path.name}'.",
                data=metadata,
            )
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to read metadata: {e}",
                error=str(e),
            )
