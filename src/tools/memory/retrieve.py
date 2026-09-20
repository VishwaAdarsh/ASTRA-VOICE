"""
Retrieve Memory Tool.
Searches and retrieves relevant long-term memory items matching a query context.
"""

from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.memory.manager import MemoryManager
from src.tools.base import BaseTool

logger = get_logger()


class RetrieveMemoryTool(BaseTool):
    """Tool to query and retrieve stored memories."""

    def __init__(self, config: Config | None = None, memory_manager: MemoryManager | None = None):
        self.config = config or Config()
        self.memory_manager = memory_manager or MemoryManager(config=self.config)

    @property
    def name(self) -> str:
        return "retrieve_memory"

    @property
    def description(self) -> str:
        return "Queries and retrieves relevant stored memory records."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.SAFE

    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language query or keywords to search relevant memories",
            },
            "project_id": {
                "type": "string",
                "description": "Optional project identifier to filter project-scoped memories",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of relevant memories to retrieve (default 5)",
            },
        },
        "required": ["query"],
    }

    def validate(self, parameters: dict[str, Any]) -> bool:
        return "query" in parameters and isinstance(parameters["query"], str)

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        query = str(parameters["query"]).strip()
        project_id = parameters.get("project_id")
        limit = parameters.get("limit", 5)

        try:
            results = self.memory_manager.retrieve(query=query, project_id=project_id, limit=limit)
            data_memories = [
                {
                    "id": r.memory.id,
                    "memory_id": r.memory.memory_id,
                    "content": r.memory.content,
                    "type": r.memory.type.value,
                    "score": r.relevance_score,
                    "project_id": r.memory.project_id,
                    "scope_type": r.memory.scope_type.value,
                }
                for r in results
            ]

            if not results:
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    message=f"No stored memories found for '{query}'.",
                    data={"memories": [], "count": 0},
                )

            msg = f"Retrieved {len(results)} relevant memories for '{query}'."
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=msg,
                data={"memories": data_memories, "count": len(results)},
            )
        except Exception as e:
            logger.error(f"RetrieveMemoryTool failed: {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Memory retrieval failed: {e}",
                error=str(e),
            )
