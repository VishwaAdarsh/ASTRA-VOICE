"""
Tool Execution Verification System.
Provides pre-execution validation checks and post-execution result verification.
"""

from pathlib import Path
from typing import Any
from src.brain.models import ExecutionStatus, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.tools.filesystem.paths import PathResolver

logger = get_logger()


class ToolVerifier:
    """Verifies pre-execution prerequisites and post-execution outcomes."""

    def __init__(self, config: Config | None = None, path_resolver: PathResolver | None = None):
        self.config = config or Config()
        self.resolver = path_resolver or PathResolver(config=self.config)

    def verify_pre_execution(self, tool_name: str, parameters: dict[str, Any]) -> tuple[bool, str | None]:
        """Perform pre-execution validation based on tool requirements."""
        logger.info(f"VERIFY_PRE_EXECUTION for tool '{tool_name}' (params={parameters})")

        if tool_name == "open_application":
            app_name = str(parameters.get("app_name", "")).strip().lower()
            if not app_name:
                return False, "Application name cannot be empty."
            if not self.config.is_app_allowed(app_name):
                # Check executable resolver
                if not self.config.get_app_executable(app_name):
                    return False, f"Application '{app_name}' is not in the allowlist."
            return True, None

        elif tool_name == "open_folder":
            folder_name = str(parameters.get("folder_name", "")).strip()
            if not folder_name:
                return False, "Folder name cannot be empty."
            try:
                path = self.resolver.resolve_folder(folder_name)
                if not path.exists():
                    return False, f"Folder '{folder_name}' could not be found on your computer."
            except Exception as e:
                return False, f"Invalid folder '{folder_name}': {e}"
            return True, None

        elif tool_name == "open_file":
            target = str(parameters.get("target", "")).strip()
            if not target:
                return False, "Target file cannot be empty."
            try:
                file_path = self.resolver.resolve_file(target)
                if not file_path.exists():
                    return False, f"File '{target}' does not exist."
            except Exception as e:
                return False, f"Invalid file path '{target}': {e}"
            return True, None

        elif tool_name == "open_website":
            target = str(parameters.get("target", "")).strip()
            if not target:
                return False, "Website URL or shortcut cannot be empty."
            url = self.config.resolve_url(target)
            if not url:
                return False, f"Invalid website target '{target}'."
            return True, None

        return True, None

    def verify_post_execution(
        self,
        result: ToolResult,
        tool_name: str = "",
        parameters: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Verify the returned tool result for correctness."""
        logger.info(f"VERIFY_POST_EXECUTION status={result.status.value}")

        if result.status == ExecutionStatus.SUCCESS:
            target_path_str = result.data.get("path")
            if target_path_str:
                p = Path(target_path_str)
                if tool_name in ("delete_file", "delete_folder"):
                    if p.exists():
                        result.status = ExecutionStatus.FAILED
                        result.error = f"Verification failed: '{target_path_str}' still exists."
                        result.verified = False
                        return result
                else:
                    if not p.exists():
                        result.status = ExecutionStatus.FAILED
                        result.error = f"Verification failed: '{target_path_str}' does not exist."
                        result.verified = False
                        return result

            result.verified = True
            if not result.message:
                result.message = "Operation completed successfully."

        elif result.status in (ExecutionStatus.FAILED, ExecutionStatus.INVALID_REQUEST, ExecutionStatus.DENIED, ExecutionStatus.NOT_FOUND):
            result.verified = False
            if not result.error:
                result.error = result.message or "Unspecified execution failure."

        return result
