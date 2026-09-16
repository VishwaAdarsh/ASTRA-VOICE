import random
import time
from typing import Any

from src.brain.llm.errors import (
    LLMAuthError,
    LLMConfigError,
    LLMContentPolicyError,
    LLMErrorType,
    LLMInvalidRequestError,
    LLMModelNotFoundError,
    LLMNetworkError,
    LLMProviderError,
    LLMQuotaExhaustedError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)
from src.brain.llm.factory import LLMProviderFactory
from src.brain.llm.models import DecisionType, LLMDecision, ModelConfig
from src.brain.llm.provider import LLMProvider
from src.core.health import HealthManager, HealthStatus
from src.core.logger import get_logger

logger = get_logger()


class LLMClient:
    """High-level client for executing LLM queries with safety retries, health tracking, and validation."""

    def __init__(
        self,
        config: ModelConfig,
        provider: LLMProvider | None = None,
        health_manager: HealthManager | None = None,
    ):
        self.config = config
        self.provider = provider or LLMProviderFactory.create(self.config)
        self.health_manager = health_manager

    @staticmethod
    def _user_friendly_error(error_type: LLMErrorType, err: Exception) -> str:
        """Map technical error types to user-friendly truthful messages."""
        if error_type == LLMErrorType.QUOTA_EXHAUSTED:
            return "Daily LLM quota limit reached. Please check your Gemini API quota or try again later."
        elif error_type == LLMErrorType.AUTH_FAILED:
            return "LLM authentication failed. Please check your API key configuration."
        elif error_type == LLMErrorType.RATE_LIMITED:
            return "LLM request rate limit reached. Please wait a moment before trying again."
        elif error_type == LLMErrorType.INVALID_CONFIGURATION:
            return "LLM provider configuration error."
        elif error_type == LLMErrorType.CONTENT_POLICY_ERROR:
            return "Request was blocked by safety policy filters."
        elif error_type == LLMErrorType.MODEL_NOT_FOUND:
            return "Requested LLM model was not found."
        elif error_type == LLMErrorType.NETWORK_ERROR:
            return "Unable to connect to LLM provider. Please check your network connection."
        elif error_type == LLMErrorType.TIMEOUT:
            return "LLM request timed out."
        return "LLM provider encountered an error while processing your request."

    def generate_decision(
        self,
        prompt: str,
        system_prompt: str | None = None,
        tool_schemas: list[dict[str, Any]] | None = None,
    ) -> LLMDecision:
        """Generate structured LLM decision with bounded exponential backoff retries and error isolation."""
        max_attempts = max(1, self.config.retry_count)

        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(
                    f"LLM_REQUEST attempt {attempt}/{max_attempts} (provider='{self.config.provider}', model='{self.config.model_name}')"
                )
                decision = self.provider.generate_structured(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    tool_schemas=tool_schemas,
                )

                # Record healthy status on successful inference
                if self.health_manager:
                    self.health_manager.set_status(
                        "LLM",
                        HealthStatus.HEALTHY,
                        f"Operational with provider '{self.config.provider}'",
                    )

                logger.info(
                    f"LLM_DECISION: type={decision.decision_type}, tool={decision.tool_name}, latency={decision.usage.latency_ms:.1f}ms"
                )
                return decision

            except Exception as e:
                err_type = getattr(e, "error_type", LLMErrorType.UNKNOWN_ERROR)
                is_retryable = getattr(e, "retryable", False)
                retry_after = getattr(e, "retry_after", None)
                err_msg = getattr(e, "message", str(e))

                # Update health manager diagnostics
                if self.health_manager:
                    if err_type == LLMErrorType.RATE_LIMITED:
                        self.health_manager.set_status(
                            "LLM",
                            HealthStatus.DEGRADED,
                            f"Rate limited: {err_msg}",
                        )
                    else:
                        self.health_manager.set_status(
                            "LLM",
                            HealthStatus.UNAVAILABLE,
                            f"{err_type.value}: {err_msg}",
                        )

                # Non-retryable failure: abort retries immediately (Auth, Quota, InvalidConfig, Policy)
                if not is_retryable:
                    logger.error(
                        f"LLM non-retryable error ({err_type.value}): {err_msg}. Aborting retries immediately."
                    )
                    return LLMDecision(
                        decision_type=DecisionType.ERROR,
                        error_type=err_type,
                        message=self._user_friendly_error(err_type, e),
                        reason=err_msg,
                        retryable=False,
                        retry_after=retry_after,
                    )

                # Retryable error: backoff if attempts remain
                if attempt < max_attempts:
                    if retry_after is not None and retry_after > 0:
                        backoff = min(retry_after, self.config.max_backoff)
                    else:
                        backoff = min(
                            self.config.initial_backoff * (self.config.backoff_factor ** (attempt - 1)),
                            self.config.max_backoff,
                        )
                    jitter = random.uniform(0, 0.1 * backoff)
                    sleep_sec = min(backoff + jitter, self.config.max_backoff)

                    logger.warning(
                        f"LLM attempt {attempt}/{max_attempts} failed ({err_type.value}): {err_msg}. "
                        f"Retrying in {sleep_sec:.2f}s..."
                    )
                    time.sleep(sleep_sec)
                else:
                    logger.error(
                        f"LLM max retry limit reached ({max_attempts}). Last error ({err_type.value}): {err_msg}"
                    )
                    return LLMDecision(
                        decision_type=DecisionType.ERROR,
                        error_type=err_type,
                        message="LLM provider unavailable after retries.",
                        reason=err_msg,
                        retryable=True,
                        retry_after=retry_after,
                    )

        # Fallback return in case loop completes without return
        return LLMDecision(
            decision_type=DecisionType.ERROR,
            error_type=LLMErrorType.UNKNOWN_ERROR,
            message="LLM provider call failed unexpectedly.",
            reason="Exhausted retry loop without decision",
        )

    def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate plain text with error handling."""
        try:
            return self.provider.generate(prompt=prompt, system_prompt=system_prompt)
        except Exception as e:
            err_type = getattr(e, "error_type", LLMErrorType.UNKNOWN_ERROR)
            if self.health_manager:
                self.health_manager.set_status("LLM", HealthStatus.UNAVAILABLE, f"{err_type.value}: {e}")
            raise

    def check_health(self) -> dict[str, Any]:
        """Check underlying provider health."""
        return self.provider.check_health()

    def shutdown(self) -> None:
        """Shut down underlying provider resources."""
        self.provider.shutdown()


