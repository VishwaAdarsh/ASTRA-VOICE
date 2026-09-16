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
    """Configuration container for LLM provider parameters."""

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
    api_key: str = ""

    def __post_init__(self):
        if not self.model_name and self.model:
            self.model_name = self.model
        elif self.model_name and not self.model:
            self.model = self.model_name


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

