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

    @abstractmethod
    def validate(self, parameters: dict[str, Any]) -> bool:
        """Validate input parameters before execution. Returns True if valid."""
        pass

    @abstractmethod
    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        """Execute tool logic and return structured ToolResult."""
        pass
