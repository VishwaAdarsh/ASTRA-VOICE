"""
Tool Selection Schema Builder.
Dynamically generates standardized OpenAPI/JSON tool schemas directly from ToolRegistry for LLM providers.
"""

from typing import TYPE_CHECKING, Any
from src.core.logger import get_logger

if TYPE_CHECKING:
    from src.tools.registry import ToolRegistry

logger = get_logger()


def generate_tool_schemas(registry: "ToolRegistry") -> list[dict[str, Any]]:
    """Convert registered BaseTool instances in registry into structured schemas for the LLM.
    
    Filters internal tools, validates schemas, and prevents duplicates.
    """
    schemas: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    for tool_name in registry.list_tools():
        try:
            tool = registry.get(tool_name)
            
            # Check if tool is explicitly exposed to LLM
            if not getattr(tool, "expose_to_llm", True):
                logger.debug(f"Excluding internal tool '{tool_name}' from LLM schema.")
                continue

            # Prevent duplicates
            normalized_name = tool.name.strip().lower()
            if normalized_name in seen_names:
                logger.warning(f"Duplicate tool name '{normalized_name}' detected in schema builder. Skipping.")
                continue

            # Build schema from tool contract
            if hasattr(tool, "get_schema"):
                schema = tool.get_schema()
            else:
                schema = {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": getattr(tool, "parameters_schema", {"type": "object", "properties": {}, "required": []}),
                }

            # Validate schema integrity
            if not schema.get("name") or not schema.get("description"):
                logger.error(f"Malformed tool schema for tool '{tool_name}': Missing name or description.")
                continue

            schemas.append(schema)
            seen_names.add(normalized_name)

        except Exception as e:
            logger.error(f"Error generating schema for tool '{tool_name}': {e}")
            continue

    return schemas
