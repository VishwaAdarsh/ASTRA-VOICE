"""
ASTRA Capability Schema Adapter.
Converts CapabilityDefinition objects into structured, provider-compatible schemas for LLM tool calling.
"""

import platform
from typing import Any, Optional
from src.core.capabilities.models import CapabilityCategory, CapabilityDefinition


class LLMToolSchemaAdapter:
    """
    Adapter converting internal CapabilityDefinition instances into standard
    OpenAI / Gemini function calling schemas for LLM prompts.
    """

    @classmethod
    def to_tool_schema(
        cls,
        capability: CapabilityDefinition,
        use_short_name: bool = True,
    ) -> dict[str, Any]:
        """
        Convert a single CapabilityDefinition to an LLM tool schema dictionary.
        
        Args:
            capability: The capability to convert.
            use_short_name: If True, uses the legacy tool name (e.g. 'open_application')
                            derived from the capability ID ('system.open_application')
                            for backward compatibility with existing prompts and model weights.
        """
        tool_name = (
            capability.capability_id.split(".")[-1]
            if use_short_name and "." in capability.capability_id
            else capability.capability_id
        )

        return {
            "name": tool_name,
            "description": capability.description,
            "parameters": capability.input_schema or {"type": "object", "properties": {}, "required": []},
        }

    @classmethod
    def generate_schemas(
        cls,
        capabilities: list[CapabilityDefinition],
        current_platform: Optional[str] = None,
        category: Optional[CapabilityCategory] = None,
        use_short_name: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Filter and convert active capabilities into a list of LLM tool schemas.
        
        Filters applied:
        - Only executable capabilities (ENABLED or REGISTERED).
        - Platform compatibility (e.g. Windows only).
        - Optional category filter.
        """
        target_platform = (current_platform or platform.system()).lower()
        schemas: list[dict[str, Any]] = []
        seen_names: set[str] = set()

        for cap in capabilities:
            # 1. State check
            if not cap.is_executable():
                continue

            # 2. Platform check
            if not cap.is_available_on_platform(target_platform):
                continue

            # 3. Category filter
            if category and cap.category != category:
                continue

            # 4. Generate schema
            schema = cls.to_tool_schema(cap, use_short_name=use_short_name)
            name = schema["name"]

            # Deduplication
            if name in seen_names:
                continue

            seen_names.add(name)
            schemas.append(schema)

        return schemas
