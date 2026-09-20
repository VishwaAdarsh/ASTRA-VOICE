"""
Central Tool Registry.
Ensures only explicitly registered, allowlisted tools can be executed.
Arbitrary function or shell execution is strictly prohibited.
"""

from typing import Any, Optional
from src.core.capabilities.models import (
    CapabilityCategory,
    CapabilityDefinition,
    CapabilityState,
    RiskLevel,
)
from src.core.capabilities.registry import CapabilityRegistry
from src.core.exceptions import ToolError, ToolNotFoundError
from src.core.logger import get_logger
from src.tools.base import BaseTool

logger = get_logger()

# Canonical metadata mapping for standard ASTRA tools
DEFAULT_TOOL_METADATA: dict[str, dict[str, Any]] = {
    "open_application": {"category": CapabilityCategory.SYSTEM, "risk": RiskLevel.RISK_2, "platforms": ["windows"], "reversible": True},
    "close_application": {"category": CapabilityCategory.SYSTEM, "risk": RiskLevel.RISK_2, "platforms": ["windows"], "reversible": True},
    "open_project": {"category": CapabilityCategory.SYSTEM, "risk": RiskLevel.RISK_2, "platforms": ["windows"], "reversible": True},
    "application_status": {"category": CapabilityCategory.SYSTEM, "risk": RiskLevel.RISK_1, "platforms": ["windows"], "read_only": True},
    "open_website": {"category": CapabilityCategory.WEB, "risk": RiskLevel.RISK_2, "platforms": ["windows", "linux", "darwin"], "reversible": True},
    "search_web": {"category": CapabilityCategory.WEB, "risk": RiskLevel.RISK_1, "platforms": ["windows", "linux", "darwin"], "read_only": True, "dependencies": ["Web"]},
    "fetch_webpage": {"category": CapabilityCategory.WEB, "risk": RiskLevel.RISK_1, "platforms": ["windows", "linux", "darwin"], "read_only": True, "dependencies": ["Web"]},
    "research_topic": {"category": CapabilityCategory.WEB, "risk": RiskLevel.RISK_1, "platforms": ["windows", "linux", "darwin"], "read_only": True, "dependencies": ["Web"]},
    "system_information": {"category": CapabilityCategory.SYSTEM, "risk": RiskLevel.RISK_1, "platforms": ["windows"], "read_only": True},
    "resource_information": {"category": CapabilityCategory.SYSTEM, "risk": RiskLevel.RISK_1, "platforms": ["windows"], "read_only": True},
    "screenshot": {"category": CapabilityCategory.SYSTEM, "risk": RiskLevel.RISK_1, "platforms": ["windows"], "read_only": True},
    "volume_control": {"category": CapabilityCategory.SYSTEM, "risk": RiskLevel.RISK_2, "platforms": ["windows"], "reversible": True},
    "open_folder": {"category": CapabilityCategory.FILESYSTEM, "risk": RiskLevel.RISK_2, "platforms": ["windows"], "reversible": True},
    "search_files": {"category": CapabilityCategory.FILESYSTEM, "risk": RiskLevel.RISK_1, "platforms": ["windows", "linux", "darwin"], "read_only": True},
    "file_metadata": {"category": CapabilityCategory.FILESYSTEM, "risk": RiskLevel.RISK_1, "platforms": ["windows", "linux", "darwin"], "read_only": True},
    "open_file": {"category": CapabilityCategory.FILESYSTEM, "risk": RiskLevel.RISK_2, "platforms": ["windows"], "reversible": True},
    "create_folder": {"category": CapabilityCategory.FILESYSTEM, "risk": RiskLevel.RISK_2, "platforms": ["windows", "linux", "darwin"], "reversible": True},
    "create_text_file": {"category": CapabilityCategory.FILESYSTEM, "risk": RiskLevel.RISK_2, "platforms": ["windows", "linux", "darwin"], "reversible": True},
    "rename_file": {"category": CapabilityCategory.FILESYSTEM, "risk": RiskLevel.RISK_3, "platforms": ["windows", "linux", "darwin"], "reversible": True},
    "move_file": {"category": CapabilityCategory.FILESYSTEM, "risk": RiskLevel.RISK_3, "platforms": ["windows", "linux", "darwin"], "reversible": True},
    "copy_file": {"category": CapabilityCategory.FILESYSTEM, "risk": RiskLevel.RISK_2, "platforms": ["windows", "linux", "darwin"], "reversible": True},
    "delete_file": {"category": CapabilityCategory.FILESYSTEM, "risk": RiskLevel.RISK_4, "platforms": ["windows", "linux", "darwin"], "requires_confirmation": True},
    "organize_folder": {"category": CapabilityCategory.FILESYSTEM, "risk": RiskLevel.RISK_3, "platforms": ["windows", "linux", "darwin"], "requires_confirmation": True, "reversible": True},
    "remember": {"category": CapabilityCategory.MEMORY, "risk": RiskLevel.RISK_2, "platforms": ["windows", "linux", "darwin"], "dependencies": ["Database"], "reversible": True},
    "retrieve_memory": {"category": CapabilityCategory.MEMORY, "risk": RiskLevel.RISK_1, "platforms": ["windows", "linux", "darwin"], "dependencies": ["Database"], "read_only": True},
    "forget_memory": {"category": CapabilityCategory.MEMORY, "risk": RiskLevel.RISK_3, "platforms": ["windows", "linux", "darwin"], "dependencies": ["Database"], "requires_confirmation": True},
    "list_memories": {"category": CapabilityCategory.MEMORY, "risk": RiskLevel.RISK_1, "platforms": ["windows", "linux", "darwin"], "dependencies": ["Database"], "read_only": True},
    "analyze_screen": {"category": CapabilityCategory.VISION, "risk": RiskLevel.RISK_1, "platforms": ["windows"], "dependencies": ["Vision"], "read_only": True},
    "analyze_active_window": {"category": CapabilityCategory.VISION, "risk": RiskLevel.RISK_1, "platforms": ["windows"], "dependencies": ["Vision"], "read_only": True},
    "analyze_image": {"category": CapabilityCategory.VISION, "risk": RiskLevel.RISK_1, "platforms": ["windows", "linux", "darwin"], "dependencies": ["Vision"], "read_only": True},
    "read_screen_text": {"category": CapabilityCategory.VISION, "risk": RiskLevel.RISK_1, "platforms": ["windows"], "dependencies": ["OCR"], "read_only": True},
}


class ToolRegistry:
    """
    Registry holding all approved, executable ASTRA tools.
    Evolved in Phase V2-10 to bridge directly with the Central CapabilityRegistry.
    """

    def __init__(self, capability_registry: Optional[CapabilityRegistry] = None):
        self._tools: dict[str, BaseTool] = {}
        self.capability_registry = capability_registry or CapabilityRegistry()

    def register(self, tool: BaseTool) -> None:
        """Register a new tool instance and declare its capability in CapabilityRegistry."""
        if not isinstance(tool, BaseTool):
            raise ToolError(f"Cannot register object {tool}: Must inherit from BaseTool.")

        tool_name = tool.name.strip().lower()
        if tool_name in self._tools:
            logger.warning(f"Overwriting already registered tool '{tool_name}'")

        self._tools[tool_name] = tool

        # Build and register corresponding CapabilityDefinition
        meta = DEFAULT_TOOL_METADATA.get(tool_name, {})
        category = meta.get("category", CapabilityCategory.OTHER)
        cap_id = getattr(tool, "capability_id", f"{category.value}.{tool_name}")
        risk = meta.get("risk", RiskLevel.RISK_2)
        platforms = meta.get("platforms", ["windows"])
        dependencies = meta.get("dependencies", [])
        read_only = meta.get("read_only", False)
        reversible = meta.get("reversible", False)
        requires_conf = meta.get("requires_confirmation", getattr(tool, "permission_level", None) == "CONFIRM")

        cap_def = CapabilityDefinition(
            capability_id=cap_id,
            name=tool.name,
            description=tool.description,
            category=category,
            risk_level=risk,
            input_schema=getattr(tool, "parameters_schema", {"type": "object", "properties": {}, "required": []}),
            requires_confirmation=requires_conf,
            read_only=read_only,
            reversible=reversible,
            platforms=platforms,
            dependencies=dependencies,
            state=CapabilityState.ENABLED,
            handler=tool,
        )

        if not self.capability_registry.exists(cap_id):
            self.capability_registry.register(cap_def)
        else:
            # Update handler
            existing_cap = self.capability_registry.get(cap_id)
            existing_cap.handler = tool

        logger.info(f"Tool '{tool_name}' registered successfully as capability '{cap_id}'.")

    def get(self, name: str) -> BaseTool:
        """Retrieve a tool by tool name or capability ID, or raise ToolNotFoundError."""
        tool_name = name.strip().lower()
        if tool_name in self._tools:
            return self._tools[tool_name]

        # Check if requested by capability ID
        if self.capability_registry.exists(tool_name):
            cap = self.capability_registry.get(tool_name)
            if cap.handler and isinstance(cap.handler, BaseTool):
                return cap.handler

        raise ToolNotFoundError(name)

    def contains(self, name: str) -> bool:
        """Check if a tool name or capability ID is registered."""
        normalized = name.strip().lower()
        return normalized in self._tools or self.capability_registry.exists(normalized)

    def has_tool(self, name: str) -> bool:
        """Alias for contains(). Check if a tool name is registered."""
        return self.contains(name)

    def list_tools(self) -> list[str]:
        """List names of all registered tools."""
        return sorted(list(self._tools.keys()))

