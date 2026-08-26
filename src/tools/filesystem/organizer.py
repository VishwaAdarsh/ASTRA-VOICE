"""
Folder Organizer Tool.
Categorizes folder items into organized subdirectories with dry-run preview mode support and CONFIRM policy.
"""

from pathlib import Path
from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.tools.base import BaseTool
from src.tools.filesystem.paths import PathResolver

logger = get_logger()


class OrganizeFolderTool(BaseTool):
    """Tool to organize a folder's contents by file extensions."""

    CATEGORY_MAP = {
        "Documents": [".pdf", ".docx", ".doc", ".txt", ".xlsx", ".pptx", ".md"],
        "Images": [".jpg", ".jpeg", ".png", ".gif", ".svg", ".bmp"],
        "Archives": [".zip", ".tar", ".gz", ".rar", ".7z"],
        "Code": [".py", ".js", ".ts", ".html", ".css", ".json", ".cpp", ".java"],
    }

    def __init__(self, config: Config | None = None, path_resolver: PathResolver | None = None):
        self.config = config or Config()
        self.resolver = path_resolver or PathResolver(config=self.config)

    @property
    def name(self) -> str:
        return "organize_folder"

    @property
    def description(self) -> str:
        return "Organizes files in a target folder into subdirectories (Documents, Images, Archives, Code). Supports preview mode."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.CONFIRM

    def validate(self, parameters: dict[str, Any]) -> bool:
        return isinstance(parameters, dict)

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        folder_str = str(parameters.get("folder", "Downloads"))
        dry_run = bool(parameters.get("dry_run", False))

        try:
            target_folder = self.resolver.resolve_folder(folder_str)
            if not target_folder.exists():
                return ToolResult(
                    status=ExecutionStatus.NOT_FOUND,
                    message=f"Folder '{folder_str}' does not exist.",
                )

            proposed_plan = []
            for item in target_folder.iterdir():
                if item.is_file() and not item.name.startswith("."):
                    ext = item.suffix.lower()
                    target_category = "Misc"
                    for cat, ext_list in self.CATEGORY_MAP.items():
                        if ext in ext_list:
                            target_category = cat
                            break

                    dest_dir = target_folder / target_category
                    dest_file = dest_dir / item.name

                    proposed_plan.append({
                        "file": item.name,
                        "source": str(item),
                        "category": target_category,
                        "destination": str(dest_file),
                    })

                    if not dry_run:
                        dest_dir.mkdir(exist_ok=True)
                        if not dest_file.exists():
                            item.rename(dest_file)

            mode_str = "Dry Run Preview" if dry_run else "Executed"
            msg = f"{mode_str}: Organized {len(proposed_plan)} files in '{target_folder.name}'."
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=msg,
                data={"plan": proposed_plan, "count": len(proposed_plan), "dry_run": dry_run},
            )
        except Exception as e:
            logger.error(f"OrganizeFolderTool failed: {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to organize folder: {e}",
                error=str(e),
            )
