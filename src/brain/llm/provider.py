"""
Abstract LLM Provider Interface.
All LLM adapters (Cloud, Local, Mock) must implement LLMProvider.
"""

from abc import ABC, abstractmethod
from typing import Any, Iterator
from src.brain.llm.models import LLMDecision, ModelConfig


class LLMProvider(ABC):
    """Abstract interface for provider-independent LLM inference."""

    def __init__(self, config: ModelConfig | None = None):
        self.config = config or ModelConfig()
        self.capabilities: set[str] = {"text", "structured"}

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

    def generate_stream(self, prompt: str, system_prompt: str | None = None) -> Iterator[str]:
        """Stream generated text chunks. Subclasses implement if supported."""
        raise NotImplementedError(f"{self.__class__.__name__} does not support streaming")

    def check_health(self) -> dict[str, Any]:
        """Check provider health and connectivity."""
        return {
            "status": "unknown",
            "provider": self.config.provider,
            "model": self.config.model_name,
        }

    def shutdown(self) -> None:
        """Clean up provider resources / connections."""
        pass

