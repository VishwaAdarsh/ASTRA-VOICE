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

    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "scope_type": {
                "type": "string",
                "enum": ["GLOBAL", "PROJECT", "SESSION"],
                "description": "Filter by memory scope",
            },
            "project_id": {
                "type": "string",
                "description": "Filter by project identifier",
            },
            "status": {
                "type": "string",
                "enum": ["ACTIVE", "SUPERSEDED", "EXPIRED", "ARCHIVED", "REVOKED"],
                "description": "Filter by lifecycle status (defaults to ACTIVE)",
            },
        },
    }

    def validate(self, parameters: dict[str, Any]) -> bool:
        return isinstance(parameters, dict)

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        try:
            from src.memory.models import MemoryScope, MemoryStatus

            scope_str = parameters.get("scope_type")
            scope_type = MemoryScope(scope_str.upper()) if scope_str and scope_str.upper() in MemoryScope.__members__ else None
            project_id = parameters.get("project_id")
            status_str = parameters.get("status", "ACTIVE")
            status = MemoryStatus(status_str.upper()) if status_str and status_str.upper() in MemoryStatus.__members__ else MemoryStatus.ACTIVE

            items = self.memory_manager.list_all(status=status, scope_type=scope_type, project_id=project_id)
            stats = self.memory_manager.get_stats()

            data_items = [
                {
                    "id": item.id,
                    "memory_id": item.memory_id,
                    "content": item.content,
                    "type": item.type.value,
                    "scope_type": item.scope_type.value,
                    "project_id": item.project_id,
                    "status": item.status.value,
                    "confidence": item.confidence,
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
