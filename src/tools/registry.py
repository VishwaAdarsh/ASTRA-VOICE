"""
Central Tool Registry.
Ensures only explicitly registered, allowlisted tools can be executed.
Arbitrary function or shell execution is strictly prohibited.
"""

from src.core.exceptions import ToolError, ToolNotFoundError
from src.core.logger import get_logger
from src.tools.base import BaseTool

logger = get_logger()


class ToolRegistry:
    """Registry holding all approved, executable ASTRA tools."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a new tool instance."""
        if not isinstance(tool, BaseTool):
            raise ToolError(f"Cannot register object {tool}: Must inherit from BaseTool.")

        tool_name = tool.name.strip().lower()
        if tool_name in self._tools:
            logger.warning(f"Overwriting already registered tool '{tool_name}'")

        self._tools[tool_name] = tool
        logger.info(f"Tool '{tool_name}' registered successfully.")

    def get(self, name: str) -> BaseTool:
        """Retrieve a tool by name or raise ToolNotFoundError."""
        tool_name = name.strip().lower()
        if tool_name not in self._tools:
            raise ToolNotFoundError(name)
        return self._tools[tool_name]

    def contains(self, name: str) -> bool:
        """Check if a tool name is registered."""
        return name.strip().lower() in self._tools

    def has_tool(self, name: str) -> bool:
        """Alias for contains(). Check if a tool name is registered."""
        return self.contains(name)


    def list_tools(self) -> list[str]:
        """List names of all registered tools."""
        return sorted(list(self._tools.keys()))
