"""
LLM Provider Factory.
Creates configured LLMProvider instances based on application configuration.
Enforces explicit provider resolution without silent fallbacks.
"""

from typing import Type
from src.brain.llm.mock_provider import MockLLMProvider
from src.brain.llm.models import ModelConfig
from src.brain.llm.provider import LLMProvider
from src.core.exceptions import LLMProviderError
from src.core.logger import get_logger

logger = get_logger()


class LLMProviderFactory:
    """Factory for instantiating LLM providers explicitly."""

    _registry: dict[str, Type[LLMProvider]] = {}

    @classmethod
    def register(cls, provider_name: str, provider_cls: Type[LLMProvider]) -> None:
        """Register an LLM provider implementation class (Registration Point for Phase 14+)."""
        key = provider_name.strip().lower()
        cls._registry[key] = provider_cls
        logger.info(f"Registered LLM provider '{key}' -> {provider_cls.__name__}")

    @classmethod
    def create(cls, config: ModelConfig) -> LLMProvider:
        provider_name = config.provider.strip().lower()
        logger.info(f"Creating LLMProvider for '{provider_name}' (model={config.model})")

        # Explicit Mock / Test Provider Selection
        if provider_name in ("mock", "test", "default"):
            return MockLLMProvider(config=config)

        # Registration Point for Phase 14 Gemini Provider
        if provider_name in ("gemini", "google_gemini", "google-gemini"):
            if "gemini" in cls._registry:
                return cls._registry["gemini"](config=config)
            raise LLMProviderError(
                f"LLM Provider '{config.provider}' is reserved for Phase 14 and is not implemented yet. "
                "Set LLM_PROVIDER=mock for development/testing."
            )

        # Dynamically Registered Provider Check
        if provider_name in cls._registry:
            return cls._registry[provider_name](config=config)

        # Explicit Error: No silent fallback permitted
        raise LLMProviderError(
            f"Unsupported or unregistered LLM Provider '{config.provider}'. "
            "No silent fallback permitted. Available providers: 'mock'."
        )
