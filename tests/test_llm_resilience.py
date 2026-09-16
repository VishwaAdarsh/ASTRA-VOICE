"""
Unit and Integration tests for LLM Provider Resilience, Error Classification,
Bounded Retry/Backoff, and Health Tracking (Phase V2-02).
"""

from unittest.mock import MagicMock, patch
import pytest

from src.brain.agent import AstraAgent
from src.brain.llm.client import LLMClient
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
from src.brain.llm.gemini_provider import GeminiProvider
from src.brain.llm.models import DecisionType, LLMDecision, ModelConfig
from src.brain.llm.provider import LLMProvider
from src.brain.models import Command, ExecutionStatus
from src.core.config import Config
from src.core.health import HealthManager, HealthStatus


class DummyFailingProvider(LLMProvider):
    """Test helper provider that simulates specific error scenarios."""

    def __init__(self, error_to_raise: Exception, config: ModelConfig | None = None):
        super().__init__(config=config)
        self.error_to_raise = error_to_raise
        self.call_count = 0

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        self.call_count += 1
        raise self.error_to_raise

    def generate_structured(
        self,
        prompt: str,
        system_prompt: str | None = None,
        tool_schemas: list[dict] | None = None,
    ) -> LLMDecision:
        self.call_count += 1
        raise self.error_to_raise


# ============================================================================
# 1. FACTORY VALIDATION & ZERO-MOCK-FALLBACK TESTS
# ============================================================================

def test_factory_rejects_unknown_provider():
    """Factory must raise LLMConfigError on unknown provider without silent fallback."""
    config = ModelConfig(provider="unsupported_quantum_llm")
    with pytest.raises(LLMConfigError) as excinfo:
        LLMProviderFactory.create(config)
    assert "No silent fallback permitted" in str(excinfo.value)
    assert excinfo.value.error_type == LLMErrorType.INVALID_CONFIGURATION


def test_factory_rejects_deferred_providers():
    """Factory must raise NotImplementedError for providers deferred to Phase V2-20."""
    for deferred in ["openai", "anthropic", "claude", "ollama", "local"]:
        config = ModelConfig(provider=deferred)
        with pytest.raises(NotImplementedError) as excinfo:
            LLMProviderFactory.create(config)
        assert "deferred to a future phase" in str(excinfo.value)


# ============================================================================
# 2. GEMINI PROVIDER INITIALIZATION & ERROR CLASSIFICATION
# ============================================================================

def test_gemini_provider_requires_api_key(monkeypatch):
    """GeminiProvider must raise LLMConfigError if API key is not configured."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("ASTRA_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    config = ModelConfig(provider="gemini", api_key="")
    with pytest.raises(LLMConfigError) as excinfo:
        GeminiProvider(config=config)
    assert "Gemini API key is missing" in str(excinfo.value)
    assert excinfo.value.error_type == LLMErrorType.INVALID_CONFIGURATION


def test_gemini_error_classification():
    """Verify GeminiProvider._classify_api_error correctly categorizes raw errors."""
    with patch("src.brain.llm.gemini_provider.genai.Client"):
        provider = GeminiProvider(config=ModelConfig(provider="gemini", api_key="fake-test-key"))

    # 1. Auth failure (401/403)
    mock_auth_err = MagicMock()
    mock_auth_err.code = 401
    mock_auth_err.__str__.return_value = "API key not valid. Please pass a valid API key."
    classified = provider._classify_api_error(mock_auth_err)
    assert isinstance(classified, LLMAuthError)
    assert classified.error_type == LLMErrorType.AUTH_FAILED
    assert not classified.retryable

    # 2. Daily Quota Exhaustion (429 with GenerateRequestsPerDay)
    mock_quota_err = MagicMock()
    mock_quota_err.code = 429
    mock_quota_err.__str__.return_value = (
        "Resource has been exhausted (e.g. check quota). "
        "Quota exceeded for quota metric 'GenerateRequestsPerDayPerProjectPerModel-FreeTier' limit: 20"
    )
    classified = provider._classify_api_error(mock_quota_err)
    assert isinstance(classified, LLMQuotaExhaustedError)
    assert classified.error_type == LLMErrorType.QUOTA_EXHAUSTED
    assert not classified.retryable

    # 3. Rate Limit (429 per-minute with retry after hint)
    mock_rate_err = MagicMock()
    mock_rate_err.code = 429
    mock_rate_err.__str__.return_value = "Rate limit exceeded. Please retry after 12s."
    classified = provider._classify_api_error(mock_rate_err)
    assert isinstance(classified, LLMRateLimitError)
    assert classified.error_type == LLMErrorType.RATE_LIMITED
    assert classified.retryable
    assert classified.retry_after == 12.0

    # 4. Model Not Found (404)
    mock_404_err = MagicMock()
    mock_404_err.code = 404
    mock_404_err.__str__.return_value = "models/nonexistent-model is not found."
    classified = provider._classify_api_error(mock_404_err)
    assert isinstance(classified, LLMModelNotFoundError)
    assert not classified.retryable

    # 5. Service Unavailable (503)
    mock_503_err = MagicMock()
    mock_503_err.code = 503
    mock_503_err.__str__.return_value = "The service is temporarily unavailable."
    classified = provider._classify_api_error(mock_503_err)
    assert isinstance(classified, LLMServiceUnavailableError)
    assert classified.retryable


def test_gemini_generic_error_classification():
    """Verify generic network/timeout error classification."""
    with patch("src.brain.llm.gemini_provider.genai.Client"):
        provider = GeminiProvider(config=ModelConfig(provider="gemini", api_key="fake-test-key"))

    timeout_err = TimeoutError("Request timed out after 10 seconds")
    c1 = provider._classify_generic_error(timeout_err)
    assert isinstance(c1, LLMTimeoutError)
    assert c1.retryable

    conn_err = ConnectionResetError("Connection reset by peer")
    c2 = provider._classify_generic_error(conn_err)
    assert isinstance(c2, LLMNetworkError)
    assert c2.retryable


# ============================================================================
# 3. BOUNDED RETRY, BACKOFF, & HEALTH TRACKING
# ============================================================================

def test_client_aborts_immediately_on_non_retryable_error():
    """Client must NOT retry when encountering non-retryable errors (e.g. QuotaExhausted)."""
    health = HealthManager()
    quota_err = LLMQuotaExhaustedError("Daily quota reached", status_code=429)
    failing_provider = DummyFailingProvider(error_to_raise=quota_err)

    client = LLMClient(
        config=ModelConfig(retry_count=5, initial_backoff=0.01),
        provider=failing_provider,
        health_manager=health,
    )

    decision = client.generate_decision("Hello ASTRA")

    # Exactly 1 call made (no useless retries)
    assert failing_provider.call_count == 1
    assert decision.decision_type == DecisionType.ERROR
    assert decision.error_type == LLMErrorType.QUOTA_EXHAUSTED
    assert not decision.retryable
    assert "quota limit reached" in decision.message.lower()

    # HealthManager status set to UNAVAILABLE
    llm_health = health.get_status("LLM")
    assert llm_health.status == HealthStatus.UNAVAILABLE


def test_client_retries_bounded_times_on_retryable_error():
    """Client must retry up to configured retry_count on retryable errors."""
    health = HealthManager()
    rate_err = LLMRateLimitError("Per-minute rate limit hit", status_code=429, retry_after=0.01)
    failing_provider = DummyFailingProvider(error_to_raise=rate_err)

    client = LLMClient(
        config=ModelConfig(retry_count=3, initial_backoff=0.01, max_backoff=0.05),
        provider=failing_provider,
        health_manager=health,
    )

    decision = client.generate_decision("Open calculator")

    # 3 attempts made
    assert failing_provider.call_count == 3
    assert decision.decision_type == DecisionType.ERROR
    assert decision.error_type == LLMErrorType.RATE_LIMITED
    assert decision.retryable

    # Health updated to DEGRADED
    llm_health = health.get_status("LLM")
    assert llm_health.status == HealthStatus.DEGRADED


def test_client_health_healthy_on_success():
    """Successful decision resets HealthManager to HEALTHY."""
    health = HealthManager()
    client = LLMClient(
        config=ModelConfig(provider="mock"),
        health_manager=health,
    )

    decision = client.generate_decision("hello")
    assert decision.decision_type == DecisionType.RESPONSE

    llm_health = health.get_status("LLM")
    assert llm_health.status == HealthStatus.HEALTHY


# ============================================================================
# 4. AGENT INTEGRATION & TRUTHFUL FALLBACK REPORTING
# ============================================================================

def test_agent_truthful_response_on_llm_failure():
    """When LLM encounters an unrecoverable failure and command is unknown, agent explains error."""
    quota_err = LLMQuotaExhaustedError("FreeTier daily quota exceeded (limit: 20)")
    failing_provider = DummyFailingProvider(error_to_raise=quota_err)

    agent = AstraAgent(llm_provider=failing_provider)

    # Command that cannot be resolved by rule-based fallback
    cmd = Command(
        raw_text="Compose an intricate poem about quantum computing",
        normalized_text="compose an intricate poem about quantum computing",
    )
    resp_text, result = agent.process_command(cmd)

    # Agent must report the LLM quota failure truthfully, not faking success
    assert "quota limit reached" in resp_text.lower()
    assert result.status == ExecutionStatus.FAILED
    assert "FreeTier daily quota exceeded" in result.error


def test_agent_graceful_offline_degradation_for_local_commands():
    """When LLM provider is down, local deterministic commands (stop, time) still work."""
    auth_err = LLMAuthError("Invalid API key", status_code=401)
    failing_provider = DummyFailingProvider(error_to_raise=auth_err)

    agent = AstraAgent(llm_provider=failing_provider)

    # Local stop command must succeed via rule-based fallback despite dead LLM
    stop_cmd = Command(raw_text="stop", normalized_text="stop")
    resp_text, result = agent.process_command(stop_cmd)
    assert "Stopped active operations" in resp_text
    assert result.status == ExecutionStatus.SUCCESS

    # Local greeting command must succeed
    hello_cmd = Command(raw_text="hello", normalized_text="hello")
    resp_text, result = agent.process_command(hello_cmd)
    assert "ASTRA" in resp_text
    assert result.status == ExecutionStatus.SUCCESS
