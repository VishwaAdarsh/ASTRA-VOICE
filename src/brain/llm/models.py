"""
LLM Subsystem Domain Models and Enums.
Defines explicit decision types, structured decision payloads, model configs, and usage metrics.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DecisionType(str, Enum):
    """Explicit decision classification types for LLM outputs."""

    TOOL_CALL = "TOOL_CALL"
    RESPONSE = "RESPONSE"
    PLAN = "PLAN"
    CLARIFICATION = "CLARIFICATION"
    REFUSAL = "REFUSAL"
    ERROR = "ERROR"


@dataclass
class ModelConfig:
    """Configuration container for LLM provider parameters.

    NOTE: ``retry_count`` is the maximum number of *attempts* performed by LLMClient
    (1 initial attempt + retry_count - 1 retries).
    """

    provider: str = "mock"
    model: str = "mock-astra-v1"
    model_name: str = ""
    temperature: float = 0.2
    max_output_tokens: int = 512
    timeout: float = 10.0
    retry_count: int = 2
    initial_backoff: float = 1.0
    max_backoff: float = 30.0
    backoff_factor: float = 2.0
    api_key: str = field(default="", repr=False)  # never include secrets in repr/logs
    # Generic HTTP provider endpoint settings (used by HTTP-based providers such as Ollama)
    base_url: str = ""
    chat_endpoint: str = ""
    # Provider "thinking" control: None = provider/model default, "false"/"true"/"low"/"medium"/"high"
    think: str | None = None

    def __post_init__(self):
        if not self.model_name and self.model:
            self.model_name = self.model
        elif self.model_name and not self.model:
            self.model = self.model_name

    @classmethod
    def from_app_config(cls, config: Any) -> "ModelConfig":
        """Build the ModelConfig for the configured provider from the application Config.

        Keeps provider-specific configuration resolution out of the Agent.
        Credentials for one provider are never passed to another provider.
        """
        provider = str(getattr(config, "llm_provider", "mock") or "mock").strip().lower()
        base = dict(
            provider=provider,
            temperature=getattr(config, "llm_temperature", 0.2),
            max_output_tokens=getattr(config, "llm_max_output_tokens", 512),
        )
        if provider == "ollama":
            return cls(
                **base,
                model=getattr(config, "ollama_model", "gemma4:31b"),
                timeout=getattr(config, "ollama_timeout", 60.0),
                # OLLAMA_MAX_RETRIES counts *retries*; LLMClient counts *attempts*.
                retry_count=max(0, int(getattr(config, "ollama_max_retries", 2))) + 1,
                api_key=getattr(config, "ollama_api_key", ""),
                base_url=getattr(config, "ollama_base_url", "https://ollama.com"),
                chat_endpoint=getattr(config, "ollama_chat_endpoint", "/api/chat"),
                think=getattr(config, "ollama_think", None),
            )
        return cls(
            **base,
            model=getattr(config, "llm_model", "mock-astra-v1"),
            timeout=getattr(config, "llm_timeout", 10.0),
            retry_count=getattr(config, "llm_retry_count", 2),
            api_key=getattr(config, "llm_api_key", ""),
        )


class ProviderHealthState(str, Enum):
    """Provider-level health state reported by LLMClient (finer-grained than HealthStatus)."""

    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    AUTH_FAILED = "AUTH_FAILED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


@dataclass
class LLMMessage:
    """Canonical provider-independent chat message."""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    name: str | None = None  # tool name for role == "tool"


@dataclass
class LLMUsage:
    """Token usage metrics and latency tracking."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0


from src.brain.llm.errors import LLMErrorType


@dataclass
class LLMDecision:
    """Structured decision output produced by the LLM Reasoning Engine."""

    decision_type: DecisionType
    tool_name: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    message: str | None = None
    reason: str | None = None
    error_type: LLMErrorType | None = None
    retry_after: float | None = None
    retryable: bool = False
    steps: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 1.0
    usage: LLMUsage = field(default_factory=LLMUsage)
    raw_response: str = ""
    # Safe provenance metadata (never contains credentials)
    provider: str | None = None
    model: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)

