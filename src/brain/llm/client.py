"""
LLM Client Engine.
Handles bounded timeouts, retries, output validation, and provider execution.
"""

from typing import Any
from src.brain.llm.factory import LLMProviderFactory
from src.brain.llm.models import DecisionType, LLMDecision, ModelConfig
from src.brain.llm.provider import LLMProvider
from src.core.exceptions import LLMProviderError, LLMValidationError
from src.core.logger import get_logger

logger = get_logger()


class LLMClient:
    """High-level client for executing LLM queries with safety retries and validation."""

    def __init__(self, config: ModelConfig, provider: LLMProvider | None = None):
        self.config = config
        self.provider = provider or LLMProviderFactory.create(self.config)

    def generate_decision(
        self,
        prompt: str,
        system_prompt: str | None = None,
        tool_schemas: list[dict[str, Any]] | None = None,
    ) -> LLMDecision:
        """Generate structured LLM decision with bounded retries and error isolation."""
        attempts = 0
        max_attempts = max(1, self.config.retry_count)

        while attempts < max_attempts:
            attempts += 1
            try:
                logger.info(f"LLM_REQUEST attempt {attempts}/{max_attempts} (model='{self.config.model}')")
                decision = self.provider.generate_structured(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    tool_schemas=tool_schemas,
                )
                logger.info(
                    f"LLM_DECISION: type={decision.decision_type}, tool={decision.tool_name}, latency={decision.usage.latency_ms:.1f}ms"
                )
                return decision
            except Exception as e:
                logger.warning(f"LLM attempt {attempts} failed: {e}")
                if attempts >= max_attempts:
                    logger.error(f"LLM max retry limit reached. Failure: {e}")
                    return LLMDecision(
                        decision_type=DecisionType.ERROR,
                        message="LLM provider unavailable.",
                        reason=str(e),
                    )
