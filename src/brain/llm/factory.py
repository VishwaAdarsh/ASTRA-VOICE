"""
LLM Provider Factory.
Creates configured LLMProvider instances based on application configuration.
Enforces explicit provider resolution without silent fallbacks.
"""

from typing import Any, Type
from src.brain.llm.errors import LLMConfigError
from src.brain.llm.gemini_provider import GeminiProvider
from src.brain.llm.mock_provider import MockLLMProvider
from src.brain.llm.models import LLMDecision, ModelConfig
from src.brain.llm.ollama_provider import OllamaProvider
from src.brain.llm.provider import LLMProvider
from src.core.logger import get_logger

logger = get_logger()

_DISABLED_NAMES = ("disabled", "none", "off")


class DisabledLLMProvider(LLMProvider):
    """Explicitly configured 'no LLM' mode (LLM_PROVIDER=disabled).

    Every call fails with a clear INVALID_CONFIGURATION error. This is NOT a fallback:
    it is only used when the operator intentionally disables the LLM.
    """

    def __init__(self, config: ModelConfig | None = None):
        super().__init__(config=config)
        self.capabilities = set()

    def _fail(self) -> None:
        raise LLMConfigError("LLM provider is disabled by configuration (LLM_PROVIDER=disabled).", provider="disabled")

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        self._fail()
        return ""

    def generate_structured(self, prompt: str, system_prompt: str | None = None, tool_schemas: list[dict[str, Any]] | None = None) -> LLMDecision:
        self._fail()
        raise AssertionError("unreachable")

    def check_health(self) -> dict[str, Any]:
        return {"status": "disabled", "provider": "disabled", "model": None}


class LLMProviderFactory:
    """Factory for instantiating LLM providers explicitly."""

    _registry: dict[str, Type[LLMProvider]] = {
        "gemini": GeminiProvider,
        "google_gemini": GeminiProvider,
        "google-gemini": GeminiProvider,
        "ollama": OllamaProvider,
    }

    _deferred_providers: set[str] = {
        "openai",
        "anthropic",
        "claude",
        "local",
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
        logger.info(f"Creating LLMProvider for '{provider_name}' (model={config.model_name})")

        # Explicit Mock / Test Provider Selection
        if provider_name in ("mock", "test", "default"):
            return MockLLMProvider(config=config)

        # Explicitly disabled LLM (operator intent, never an automatic fallback)
        if provider_name in _DISABLED_NAMES:
            return DisabledLLMProvider(config=config)

        # Real Gemini Provider Resolution
        if provider_name in ("gemini", "google_gemini", "google-gemini"):
            return GeminiProvider(config=config)

        # Real Ollama Provider Resolution (raises LLMConfigError on invalid config; never falls back)
        if provider_name == "ollama":
            return OllamaProvider(config=config)

        # Explicit check for deferred providers (Phase V2-20)
        if provider_name in cls._deferred_providers:
            raise NotImplementedError(
                f"Provider '{config.provider}' is deferred to a future phase and is not yet implemented."
            )

        # Dynamically Registered Provider Check
        if provider_name in cls._registry:
            return cls._registry[provider_name](config=config)

        # Explicit Error: No silent fallback permitted
        raise LLMConfigError(
            f"Unsupported or unregistered LLM Provider '{config.provider}'. "
            "No silent fallback permitted. Available providers: 'gemini', 'ollama', 'mock', 'disabled'.",
            provider=config.provider,
        )
