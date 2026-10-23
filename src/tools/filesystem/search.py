"""
Filesystem Search Tool.
Searches files and folders in approved trusted locations with depth bounds, execution timeouts, and max result caps.
Safe, read-only metadata retrieval with tolerance for permission errors.
"""

import os
from pathlib import Path
import time
from typing import Any

from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.exceptions import PathSecurityError
from src.core.logger import get_logger
from src.tools.base import BaseTool
from src.tools.filesystem.paths import PathResolver

logger = get_logger()

MAX_ALLOWED_DEPTH = 3
MAX_ALLOWED_RESULTS = 20
MAX_SEARCH_TIMEOUT_SEC = 5.0


class SearchFilesTool(BaseTool):
    """Tool for searching files in approved trusted locations."""

    name = "search_files"
    description = "Searches files in trusted locations (Downloads, Desktop, Documents, Projects) by query, extension, or recency."
    permission_level = PermissionLevel.SAFE

    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Keyword or filename pattern to search for (case-insensitive).",
            },
            "location": {
                "type": "string",
                "description": "Approved root directory (e.g., 'Downloads', 'Documents', 'Desktop', 'Pictures', 'Videos', 'Music').",
                "default": "Downloads",
            },
            "extension": {
                "type": "string",
                "description": "Filter by file extension (e.g. '.pdf', '.py', 'txt').",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of search results to return (capped at 20).",
                "default": 10,
            },
            "max_depth": {
                "type": "integer",
                "description": "Maximum directory traversal depth (capped at 3).",
                "default": 3,
            },
        },
    }

    def __init__(self, config: Config | None = None, path_resolver: PathResolver | None = None):
        self.config = config or Config()
        self.resolver = path_resolver or PathResolver(config=self.config)

    def validate(self, parameters: dict[str, Any]) -> bool:
        return isinstance(parameters, dict)

    def _is_location_approved(self, target_folder: Path) -> bool:
        """Verify that the target folder is within authorized roots or test sandbox."""
        resolved_target = target_folder.resolve()

        # If sandbox override is active, strictly constrain to sandbox
        if self.resolver.sandbox_root and self.resolver.sandbox_root.exists():
            try:
                resolved_sandbox = self.resolver.sandbox_root.resolve()
                return resolved_target == resolved_sandbox or resolved_target.is_relative_to(resolved_sandbox)
            except (ValueError, TypeError, OSError):
                return False

        # Specific user content roots only (exclude raw user profile home / AppData)
        safe_keys = ("downloads", "documents", "desktop", "pictures", "videos", "music")
        approved_roots: list[Path] = [
            self.config.folder_allowlist[k] for k in safe_keys if k in self.config.folder_allowlist
        ] + list(self.config.project_dirs)

        for root in approved_roots:
            try:
                resolved_root = root.resolve()
                if resolved_target == resolved_root or resolved_target.is_relative_to(resolved_root):
                    return True
            except (ValueError, TypeError, OSError):
                continue

        return False

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        start_time = time.time()
        query = str(parameters.get("query", "")).lower().strip()
        ext = str(parameters.get("extension", "")).lower().strip()
        location_str = str(parameters.get("location", "Downloads")).strip()

        # Bound result limits and traversal depth
        raw_limit = int(parameters.get("limit", self.config.max_search_results or 10))
        limit = max(1, min(raw_limit, MAX_ALLOWED_RESULTS))

        raw_depth = int(parameters.get("max_depth", MAX_ALLOWED_DEPTH))
        max_depth = max(1, min(raw_depth, MAX_ALLOWED_DEPTH))

        timeout_sec = min(float(parameters.get("timeout_sec", MAX_SEARCH_TIMEOUT_SEC)), MAX_SEARCH_TIMEOUT_SEC)

        if ext and not ext.startswith("."):
            ext = f".{ext}"

        try:
            target_folder = self.resolver.resolve_folder(location_str)
            if not target_folder.exists():
                return ToolResult(
                    status=ExecutionStatus.NOT_FOUND,
                    message=f"Location '{location_str}' does not exist.",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            # Security boundary check: ensure target is within approved roots
            if not self._is_location_approved(target_folder):
                logger.warning(f"File search rejected for unapproved location: {target_folder}")
                return ToolResult(
                    status=ExecutionStatus.DENIED,
                    message=f"Access denied: Location '{location_str}' is outside approved search roots.",
                    error="Location outside approved roots",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            results: list[dict[str, Any]] = []
            target_depth = len(target_folder.resolve().parts)
            timed_out = False

            # Bounded iterative traversal with error tolerance
            try:
                for root_dir, dirs, files in os.walk(str(target_folder)):
                    if time.time() - start_time > timeout_sec:
                        timed_out = True
                        logger.warning(f"File search timed out after {timeout_sec:.1f}s")
                        break

                    current_depth = len(Path(root_dir).parts) - target_depth
                    if current_depth >= max_depth:
                        dirs.clear()

                    # Exclude hidden or heavy directories to optimize performance
                    dirs[:] = [
                        d for d in dirs
                        if not d.startswith(".")
                        and d.lower() not in ("node_modules", "$recycle.bin", "__pycache__", "appdata")
                    ]

                    for fname in files:
                        if time.time() - start_time > timeout_sec:
                            timed_out = True
                            break

                        # Query substring filter
                        if query and query not in fname.lower():
                            continue

                        # Extension filter
                        if ext and not fname.lower().endswith(ext):
                            continue

                        file_path = Path(root_dir) / fname
                        try:
                            st = file_path.stat()
                            results.append({
                                "name": fname,
                                "path": str(file_path),
                                "parent": str(file_path.parent),
                                "extension": file_path.suffix.lower(),
                                "size": st.st_size,
                                "modified": st.st_mtime,
                            })
                        except (PermissionError, OSError):
                            # Tolerate inaccessible files gracefully
                            continue

                        if len(results) >= limit:
                            break

                    if len(results) >= limit:
                        break
            except (PermissionError, OSError) as e:
                logger.warning(f"Permission or OS notice during walk of '{target_folder}': {e}")

            # Sort by modified time descending (newest first)
            results.sort(key=lambda x: x["modified"], reverse=True)

            # Construct natural voice-friendly summary
            location_display = target_folder.name or location_str
            count = len(results)
            if count == 0:
                if query:
                    msg = f"No files matching '{query}' were found in {location_display}."
                else:
                    msg = f"No files were found in {location_display}."
            else:
                files_word = "file" if count == 1 else "files"
                if query:
                    msg = f"Found {count} {files_word} matching '{query}' in {location_display}."
                else:
                    msg = f"Found {count} {files_word} in {location_display}."

            if timed_out:
                msg += f" (Search bounded by {timeout_sec:.0f}s timeout)"

            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=msg,
                data={
                    "results": results,
                    "count": count,
                    "query": query,
                    "location": str(target_folder),
                    "timed_out": timed_out,
                },
                execution_time_ms=(time.time() - start_time) * 1000,
                verified=True,
            )

        except PathSecurityError as pse:
            logger.warning(f"PathSecurityError in SearchFilesTool: {pse}")
            return ToolResult(
                status=ExecutionStatus.DENIED,
                message=str(pse),
                error=str(pse),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            logger.error(f"SearchFilesTool error: {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Search failed: {e}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
