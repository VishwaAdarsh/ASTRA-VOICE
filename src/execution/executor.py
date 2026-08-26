"""
Tool Executor Engine.
Executes tool requests through registry validation, permission checks, pre/post verification, and error handling.
"""

import time
from src.brain.models import ExecutionStatus, PermissionLevel, ToolRequest, ToolResult
from src.core.exceptions import ToolNotFoundError
from src.core.logger import get_logger
from src.execution.verifier import ToolVerifier
from src.security.confirmation import ConfirmationHandler, ConsoleConfirmationHandler
from src.security.permissions import PermissionManager
from src.tools.registry import ToolRegistry

logger = get_logger()


class ToolExecutor:
    """Orchestrates tool execution safety pipeline."""

    def __init__(
        self,
        registry: ToolRegistry,
        permission_manager: PermissionManager,
        verifier: ToolVerifier | None = None,
        confirmation_handler: ConfirmationHandler | None = None,
    ):
        self.registry = registry
        self.permission_manager = permission_manager
        self.verifier = verifier or ToolVerifier()
        self.confirmation_handler = confirmation_handler or ConsoleConfirmationHandler()

    def execute(self, request: ToolRequest) -> ToolResult:
        """Process and execute a ToolRequest."""
        start_time = time.time()
        logger.info(f"EXECUTOR: Received request for tool '{request.tool_name}'")

        # 1. Lookup Tool in Registry
        try:
            tool = self.registry.get(request.tool_name)
        except ToolNotFoundError as e:
            logger.warning(f"EXECUTOR: Tool '{request.tool_name}' not found in registry.")
            return ToolResult(
                status=ExecutionStatus.NOT_FOUND,
                message=f"I couldn't find the tool '{request.tool_name}'.",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # 2. Pre-execution Verification
        is_valid, error_msg = self.verifier.verify_pre_execution(tool.name, request.parameters)
        if not is_valid:
            logger.warning(f"EXECUTOR: Pre-verification failed for '{tool.name}': {error_msg}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=error_msg or "Pre-execution check failed.",
                error=error_msg,
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # 3. Permission Check
        if not self.permission_manager.is_permitted(request, tool.permission_level):
            logger.warning(f"EXECUTOR: Permission denied for tool '{tool.name}'")
            return ToolResult(
                status=ExecutionStatus.DENIED,
                message=f"Action '{tool.name}' is blocked by security policy.",
                error="Permission denied",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # 4. User Confirmation check if required
        if tool.permission_level == PermissionLevel.CONFIRM:
            approved = self.confirmation_handler.confirm(
                f"Execute tool '{tool.name}' with params {request.parameters}"
            )
            if not approved:
                logger.info(f"EXECUTOR: Action '{tool.name}' canceled by user.")
                return ToolResult(
                    status=ExecutionStatus.DENIED,
                    message=f"Execution of '{tool.name}' was canceled by user.",
                    error="User denied confirmation",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

        # 5. Tool Validation
        if not tool.validate(request.parameters):
            logger.warning(f"EXECUTOR: Tool '{tool.name}' validation failed for parameters {request.parameters}")
            return ToolResult(
                status=ExecutionStatus.INVALID_REQUEST,
                message=f"Invalid parameters for '{tool.name}'.",
                error="Parameter validation failed",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # 6. Execute Tool
        try:
            logger.info(f"TOOL_EXECUTION: Executing tool '{tool.name}'")
            result = tool.execute(request.parameters)
            result.execution_time_ms = (time.time() - start_time) * 1000
        except Exception as e:
            logger.error(f"EXECUTOR: Exception thrown during tool execution '{tool.name}': {e}", exc_info=True)
            result = ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"I couldn't complete that action.",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # 7. Post-execution Verification
        verified_result = self.verifier.verify_post_execution(result)
        return verified_result
