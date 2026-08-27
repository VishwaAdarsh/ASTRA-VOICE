"""
Forget Memory Tool.
Deletes specific stored memories or clears memory records.
"""

from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.memory.manager import MemoryManager
from src.tools.base import BaseTool

logger = get_logger()


class ForgetMemoryTool(BaseTool):
    """Tool to delete specific stored memories."""

    def __init__(self, config: Config | None = None, memory_manager: MemoryManager | None = None):
        self.config = config or Config()
        self.memory_manager = memory_manager or MemoryManager(config=self.config)

    @property
    def name(self) -> str:
        return "forget_memory"

    @property
    def description(self) -> str:
        return "Deletes matching stored memory items."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.SAFE

    def validate(self, parameters: dict[str, Any]) -> bool:
        return ("target" in parameters and isinstance(parameters["target"], str)) or ("memory_id" in parameters and isinstance(parameters["memory_id"], int))

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        memory_id = parameters.get("memory_id")
        target = parameters.get("target", "").strip()

        try:
            if memory_id and isinstance(memory_id, int):
                success = self.memory_manager.forget(memory_id)
                if success:
                    return ToolResult(
                        status=ExecutionStatus.SUCCESS,
                        message=f"Memory #{memory_id} removed.",
                        data={"id": memory_id},
                    )
                return ToolResult(
                    status=ExecutionStatus.NOT_FOUND,
                    message=f"Memory #{memory_id} not found.",
                )

            if target:
                deleted_count = self.memory_manager.forget_matching(target)
                if deleted_count > 0:
                    return ToolResult(
                        status=ExecutionStatus.SUCCESS,
                        message=f"Removed {deleted_count} memory items matching '{target}'.",
                        data={"count": deleted_count},
                    )
                return ToolResult(
                    status=ExecutionStatus.NOT_FOUND,
                    message=f"No memories found matching '{target}'.",
                )

            return ToolResult(
                status=ExecutionStatus.INVALID_REQUEST,
                message="Target memory string or memory_id required.",
            )
        except Exception as e:
            logger.error(f"ForgetMemoryTool failed: {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to delete memory: {e}",
                error=str(e),
            )
