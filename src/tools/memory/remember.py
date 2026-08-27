"""
Remember Tool.
Stores explicit memory items into ASTRA persistent long-term memory.
"""

from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.memory.manager import MemoryManager
from src.memory.models import MemoryImportance, MemorySource, MemoryType
from src.tools.base import BaseTool

logger = get_logger()


class RememberTool(BaseTool):
    """Tool to explicitly store long-term memory items."""

    def __init__(self, config: Config | None = None, memory_manager: MemoryManager | None = None):
        self.config = config or Config()
        self.memory_manager = memory_manager or MemoryManager(config=self.config)

    @property
    def name(self) -> str:
        return "remember"

    @property
    def description(self) -> str:
        return "Persists a piece of information or preference into ASTRA's long-term memory."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.SAFE

    def validate(self, parameters: dict[str, Any]) -> bool:
        return "content" in parameters and isinstance(parameters["content"], str) and len(parameters["content"].strip()) > 0

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        content = str(parameters["content"]).strip()
        type_str = str(parameters.get("memory_type", "USER_FACT")).upper()

        try:
            mem_type = MemoryType(type_str) if type_str in MemoryType.__members__ else MemoryType.USER_FACT
            item = self.memory_manager.remember(
                content=content,
                memory_type=mem_type,
                source=MemorySource.USER_EXPLICIT,
                importance=MemoryImportance.HIGH,
            )

            if not item:
                return ToolResult(
                    status=ExecutionStatus.INVALID_REQUEST,
                    message="Information could not be stored due to memory privacy policies or secret filtering.",
                )

            msg = f"Saved to memory: '{content}'."
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=msg,
                data={"id": item.id, "content": item.content, "type": item.type.value},
            )
        except Exception as e:
            logger.error(f"RememberTool failed: {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to save memory: {e}",
                error=str(e),
            )
