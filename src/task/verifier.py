"""
Task Verifier Component.
Executes post-step verification strategies for executed tool steps.
"""

from pathlib import Path
from src.brain.models import ExecutionStatus, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.task.models import TaskStep, VerificationResult

logger = get_logger()


class TaskVerifier:
    """Verifies empirical outcome of executed task steps."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def verify_step(self, step: TaskStep, tool_result: ToolResult) -> VerificationResult:
        """Verify step execution outcome using evidence verification strategies."""
        if tool_result.status != ExecutionStatus.SUCCESS:
            return VerificationResult(
                success=False,
                method="STATUS_CHECK",
                evidence=str(tool_result.error),
                message=f"Tool execution reported status {tool_result.status.value}",
            )

        tool_name = step.tool_name.lower()

        # Strategy 1: File Creation Verification
        if tool_name in ("create_text_file", "copy_file", "move_file", "create_folder"):
            target_path = step.arguments.get("file_path") or step.arguments.get("destination_path") or step.arguments.get("folder_path")
            if target_path:
                p = Path(target_path)
                if p.exists():
                    return VerificationResult(
                        success=True,
                        method="FILE_SYSTEM_EXISTS",
                        evidence=f"File/Folder verified at '{p.resolve()}'",
                        message=f"Empirically verified existence of '{p.name}'",
                    )
                else:
                    return VerificationResult(
                        success=False,
                        method="FILE_SYSTEM_EXISTS",
                        evidence=f"Path '{target_path}' not found",
                        message=f"File creation verification failed for '{target_path}'",
                    )

        # Strategy 2: Web Research Verification
        if tool_name in ("search_web", "research_topic", "fetch_webpage"):
            if tool_result.data and ("sources" in tool_result.data or "summary" in tool_result.data or "content" in tool_result.data):
                return VerificationResult(
                    success=True,
                    method="WEB_DATA_STRUCTURED",
                    evidence="Valid web data payload present",
                    message="Empirically verified web research data retrieval",
                )

        # Default Verification Strategy
        return VerificationResult(
            success=True,
            method="DEFAULT_TOOL_SUCCESS",
            evidence=tool_result.message,
            message="Step completed successfully without errors",
        )
