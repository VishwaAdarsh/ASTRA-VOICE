"""
LLM Provider Factory.
Creates configured LLMProvider instances based on application configuration.
"""

from src.brain.llm.mock_provider import MockLLMProvider
from src.brain.llm.models import ModelConfig
from src.brain.llm.provider import LLMProvider
from src.core.logger import get_logger

logger = get_logger()


class LLMProviderFactory:
    """Factory for instantiating LLM providers."""

    @staticmethod
    def create(config: ModelConfig) -> LLMProvider:
        provider_name = config.provider.strip().lower()
        logger.info(f"Creating LLMProvider for '{provider_name}' (model={config.model})")

        if provider_name in ("mock", "test", "default"):
            return MockLLMProvider(config=config)
        else:
            logger.warning(
                f"Provider '{provider_name}' not natively registered. Falling back to MockLLMProvider."
            )
            return MockLLMProvider(config=config)
