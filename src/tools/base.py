"""
Base Abstract Tool Class for ASTRA.
All executable capabilities must derive from BaseTool and register with ToolRegistry.
"""

from abc import ABC, abstractmethod
from typing import Any
from src.brain.models import PermissionLevel, ToolResult


class BaseTool(ABC):
    """Abstract base class for all ASTRA tools."""

    name: str
    description: str
    permission_level: PermissionLevel = PermissionLevel.SAFE
    expose_to_llm: bool = True
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    @abstractmethod
    def validate(self, parameters: dict[str, Any]) -> bool:
        """Validate input parameters before execution. Returns True if valid."""
        pass

    @abstractmethod
    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        """Execute tool logic and return structured ToolResult."""
        pass

    def get_schema(self) -> dict[str, Any]:
        """Return standardized JSON schema describing tool metadata and parameters."""
        schema_params = getattr(
            self,
            "parameters_schema",
            {"type": "object", "properties": {}, "required": []},
        )
        return {
            "name": self.name,
            "description": self.description,
            "parameters": schema_params,
        }
