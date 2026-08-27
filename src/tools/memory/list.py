"""
List Memories Tool.
Lists summary statistics and active stored memory records.
"""

from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.memory.manager import MemoryManager
from src.tools.base import BaseTool

logger = get_logger()


class ListMemoriesTool(BaseTool):
    """Tool to list stored memory categories and records."""

    def __init__(self, config: Config | None = None, memory_manager: MemoryManager | None = None):
        self.config = config or Config()
        self.memory_manager = memory_manager or MemoryManager(config=self.config)

    @property
    def name(self) -> str:
        return "list_memories"

    @property
    def description(self) -> str:
        return "Lists summary statistics and active stored long-term memory items."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.SAFE

    def validate(self, parameters: dict[str, Any]) -> bool:
        return isinstance(parameters, dict)

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        try:
            items = self.memory_manager.list_all()
            stats = self.memory_manager.get_stats()

            data_items = [
                {
                    "id": item.id,
                    "content": item.content,
                    "type": item.type.value,
                    "source": item.source.value,
                    "created_at": item.created_at,
                }
                for item in items
            ]

            msg = f"Retrieved {len(items)} active memories ({stats['total']} total)."
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=msg,
                data={"memories": data_items, "stats": stats, "count": len(items)},
            )
        except Exception as e:
            logger.error(f"ListMemoriesTool failed: {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to list memories: {e}",
                error=str(e),
            )
