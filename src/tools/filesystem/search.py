"""
Filesystem Search Tool.
Searches files and folders in trusted locations with parameter filters and max result caps.
"""

from pathlib import Path
from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.tools.base import BaseTool
from src.tools.filesystem.paths import PathResolver

logger = get_logger()


class SearchFilesTool(BaseTool):
    """Tool for searching files in trusted locations."""

    def __init__(self, config: Config | None = None, path_resolver: PathResolver | None = None):
        self.config = config or Config()
        self.resolver = path_resolver or PathResolver(config=self.config)

    @property
    def name(self) -> str:
        return "search_files"

    @property
    def description(self) -> str:
        return "Searches files in trusted locations (Downloads, Desktop, Documents) by query, extension, or recency."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.SAFE

    def validate(self, parameters: dict[str, Any]) -> bool:
        return isinstance(parameters, dict)

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        query = str(parameters.get("query", "")).lower().strip()
        ext = str(parameters.get("extension", "")).lower().strip()
        location_str = str(parameters.get("location", "Downloads"))
        limit = min(int(parameters.get("limit", self.config.max_search_results)), 20)

        if ext and not ext.startswith("."):
            ext = f".{ext}"

        try:
            target_folder = self.resolver.resolve_folder(location_str)
            if not target_folder.exists():
                return ToolResult(
                    status=ExecutionStatus.NOT_FOUND,
                    message=f"Location '{location_str}' does not exist.",
                )

            results = []
            for item in target_folder.rglob("*"):
                if item.is_file():
                    # Filter by query
                    if query and query not in item.name.lower():
                        continue
                    # Filter by extension
                    if ext and item.suffix.lower() != ext:
                        continue

                    results.append({
                        "name": item.name,
                        "path": str(item),
                        "size": item.stat().st_size,
                        "modified": item.stat().st_mtime,
                    })

                    if len(results) >= limit:
                        break

            # Sort by modified time descending (newest first)
            results.sort(key=lambda x: x["modified"], reverse=True)

            msg = f"Found {len(results)} matching files in '{location_str}'."
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=msg,
                data={"results": results, "count": len(results)},
            )
        except Exception as e:
            logger.error(f"SearchFilesTool error: {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Search failed: {e}",
                error=str(e),
            )
