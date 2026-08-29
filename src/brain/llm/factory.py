"""
LLM Provider Factory.
Creates configured LLMProvider instances based on application configuration.
Enforces explicit provider resolution without silent fallbacks.
"""

from typing import Type
from src.brain.llm.gemini_provider import GeminiProvider
from src.brain.llm.mock_provider import MockLLMProvider
from src.brain.llm.models import ModelConfig
from src.brain.llm.provider import LLMProvider
from src.core.exceptions import LLMProviderError
from src.core.logger import get_logger

logger = get_logger()


class LLMProviderFactory:
    """Factory for instantiating LLM providers explicitly."""

    _registry: dict[str, Type[LLMProvider]] = {
        "gemini": GeminiProvider,
        "google_gemini": GeminiProvider,
        "google-gemini": GeminiProvider,
    }

    @classmethod
    def register(cls, provider_name: str, provider_cls: Type[LLMProvider]) -> None:
        """Register an LLM provider implementation class."""
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

        # Real Gemini Provider Resolution (Phase 14)
        if provider_name in ("gemini", "google_gemini", "google-gemini"):
            return GeminiProvider(config=config)

        # Dynamically Registered Provider Check
        if provider_name in cls._registry:
            return cls._registry[provider_name](config=config)

        # Explicit Error: No silent fallback permitted
        raise LLMProviderError(
            f"Unsupported or unregistered LLM Provider '{config.provider}'. "
            "No silent fallback permitted. Available providers: 'mock', 'gemini'."
        )
