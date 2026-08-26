"""
Abstract LLM Provider Interface.
All LLM adapters (Cloud, Local, Mock) must implement LLMProvider.
"""

from abc import ABC, abstractmethod
from typing import Any
from src.brain.llm.models import LLMDecision, ModelConfig


class LLMProvider(ABC):
    """Abstract interface for provider-independent LLM inference."""

    def __init__(self, config: ModelConfig | None = None):
        self.config = config or ModelConfig()

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate raw text completion."""
        pass

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        system_prompt: str | None = None,
        tool_schemas: list[dict[str, Any]] | None = None,
    ) -> LLMDecision:
        """Generate validated structured decision."""
        pass
