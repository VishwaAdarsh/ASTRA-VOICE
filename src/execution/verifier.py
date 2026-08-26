"""
Tool Execution Verification System.
Provides pre-execution validation checks and post-execution result verification.
"""

from typing import Any
from src.brain.models import ExecutionStatus, ToolResult
from src.core.config import Config
from src.core.logger import get_logger

logger = get_logger()


class ToolVerifier:
    """Verifies pre-execution prerequisites and post-execution outcomes."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def verify_pre_execution(self, tool_name: str, parameters: dict[str, Any]) -> tuple[bool, str | None]:
        """Perform pre-execution validation based on tool requirements."""
        logger.info(f"VERIFY_PRE_EXECUTION for tool '{tool_name}'")

        if tool_name == "open_application":
            app_name = parameters.get("app_name", "")
            if not self.config.is_app_allowed(app_name):
                return False, f"I couldn't find '{app_name}' in the allowed applications list."
            return True, None

        elif tool_name == "open_folder":
            folder_name = parameters.get("folder_name", "")
            path = self.config.get_folder_path(folder_name)
            if not path or not path.exists():
                return False, f"That folder could not be found."
            return True, None

        elif tool_name == "open_website":
            target = parameters.get("target", "")
            url = self.config.resolve_url(target)
            if not url:
                return False, f"Invalid website target '{target}'."
            return True, None

        elif tool_name == "system_information":
            return True, None

        return True, None

    def verify_post_execution(self, result: ToolResult) -> ToolResult:
        """Verify the returned tool result for correctness."""
        logger.info(f"VERIFY_POST_EXECUTION status={result.status}")

        if result.status == ExecutionStatus.SUCCESS:
            if not result.message:
                result.message = "Operation completed successfully."
        elif result.status == ExecutionStatus.FAILED:
            if not result.error:
                result.error = "Unspecified execution failure."

        return result
