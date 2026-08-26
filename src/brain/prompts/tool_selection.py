"""
Tool Selection Schema Builder.
Dynamically generates JSON/OpenAPI tool schemas directly from ToolRegistry.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.tools.registry import ToolRegistry


def generate_tool_schemas(registry: "ToolRegistry") -> list[dict[str, Any]]:
    """Convert registered BaseTool instances in registry into structured schemas for the LLM."""
    schemas = []
    for tool_name in registry.list_tools():
        tool = registry.get(tool_name)
        schemas.append(
            {
                "name": tool.name,
                "description": tool.description,
                "permission_level": tool.permission_level.value,
            }
        )
    return schemas
