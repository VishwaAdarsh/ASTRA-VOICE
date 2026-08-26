"""
Create Folder and Create Text File Tools.
"""

from pathlib import Path
from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.tools.base import BaseTool
from src.tools.filesystem.paths import PathResolver

logger = get_logger()


class CreateFolderTool(BaseTool):
    """Tool to create a new folder in a trusted location."""

    def __init__(self, config: Config | None = None, path_resolver: PathResolver | None = None):
        self.config = config or Config()
        self.resolver = path_resolver or PathResolver(config=self.config)

    @property
    def name(self) -> str:
        return "create_folder"

    @property
    def description(self) -> str:
        return "Creates a new folder in a trusted directory (e.g. Desktop, Documents, Downloads)."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.SAFE

    def validate(self, parameters: dict[str, Any]) -> bool:
        return "folder_name" in parameters and isinstance(parameters["folder_name"], str)

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        folder_name = str(parameters["folder_name"]).strip()
        location_str = str(parameters.get("location", "Desktop"))

        try:
            parent = self.resolver.resolve_folder(location_str)
            target_path = parent / folder_name
            self.resolver.validate_path_security(target_path)

            target_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created folder '{target_path}'")

            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Folder '{folder_name}' created successfully.",
                data={"path": str(target_path)},
            )
        except Exception as e:
            logger.error(f"CreateFolderTool failed: {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to create folder: {e}",
                error=str(e),
            )


class CreateTextFileTool(BaseTool):
    """Tool to create safe text and document files (.txt, .md)."""

    def __init__(self, config: Config | None = None, path_resolver: PathResolver | None = None):
        self.config = config or Config()
        self.resolver = path_resolver or PathResolver(config=self.config)

    @property
    def name(self) -> str:
        return "create_text_file"

    @property
    def description(self) -> str:
        return "Creates a safe text or markdown file (.txt, .md) in a trusted location."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.SAFE

    def validate(self, parameters: dict[str, Any]) -> bool:
        return "filename" in parameters and isinstance(parameters["filename"], str)

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        filename = str(parameters["filename"]).strip()
        content = str(parameters.get("content", ""))
        location_str = str(parameters.get("location", "Documents"))

        # Safety restriction: only text/markdown extensions allowed
        ext = Path(filename).suffix.lower()
        if ext in (".exe", ".bat", ".ps1", ".cmd", ".vbs", ".msi", ".dll"):
            return ToolResult(
                status=ExecutionStatus.DENIED,
                message=f"Creating executable or script files ({ext}) is strictly prohibited for security.",
            )

        try:
            parent = self.resolver.resolve_folder(location_str)
            target_path = parent / filename
            self.resolver.validate_path_security(target_path)

            target_path.write_text(content, encoding="utf-8")
            logger.info(f"Created text file '{target_path}'")

            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=f"File '{filename}' created successfully.",
                data={"path": str(target_path)},
            )
        except Exception as e:
            logger.error(f"CreateTextFileTool failed: {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to create text file: {e}",
                error=str(e),
            )
