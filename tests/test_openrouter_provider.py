"""
Tests for OpenRouter Real LLM Provider Integration (Free Models Only).

Covers Unit and Integration Test Scenarios (mocked HTTP via httpx.MockTransport):
 1. Factory selection (LLM_PROVIDER=openrouter -> OpenRouterProvider)
 2. Missing API key (fails closed with LLMConfigError)
 3. Default model (defaults to 'openrouter/free')
 4. Cost protection (only free models allowed unless OPENROUTER_ALLOW_PAID_MODELS=true)
 5. Request headers & payload (Bearer auth, optional site/app headers, OpenAI chat completions shape)
 6. Successful text generation (choices[0].message.content -> LLMDecision)
 7. Inline thinking block suppression (<think>...</think> stripped)
 8. Tool call normalization (OpenRouter tool_calls -> canonical schema)
 9. Tool call arguments parsing (JSON string -> dict)
10. Malformed arguments error handling (invalid JSON -> LLMProviderError)
11. Empty response error handling (empty content & tool calls -> LLMProviderError)
12. Unauthorized error (401 / 403 -> LLMAuthError, non-retryable)
13. Credit / payment error (402 -> LLMQuotaExhaustedError, non-retryable)
14. Rate limit & Retry-After (429 -> LLMRateLimitError, retryable)
15. Quota exhaustion (429 with quota hints -> LLMQuotaExhaustedError)
16. Model not found (404 -> LLMModelNotFoundError)
17. Timeout error (httpx.TimeoutException -> LLMTimeoutError, retryable)
18. Network error (httpx.TransportError -> LLMNetworkError, retryable)
19. 5xx upstream server error (500 / 502 / 503 -> LLMServiceUnavailableError, retryable)
20. Secret redaction (API key never in repr, logs, or exceptions)
21. Health check & is_free reporting
22. Agent end-to-end integration (AstraAgent + OpenRouter + tool execution)
23. No double tool execution on failure
24. Fallback failover handling
25. Opt-in live API smoke test (skips cleanly when OPENROUTER_API_KEY is not set)
"""

import json
import logging
import os
from typing import Any
from unittest.mock import MagicMock, patch
import httpx
import pytest

from src.brain.agent import AstraAgent
from src.brain.llm.client import LLMClient
from src.brain.llm.errors import (
    LLMAuthError,
    LLMConfigError,
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
from src.brain.llm.models import (
    DecisionType,
    LLMDecision,
    LLMMessage,
    ModelConfig,
    ProviderHealthState,
)
from src.brain.llm.openrouter_provider import OpenRouterProvider
from src.brain.models import Command, ExecutionStatus
from src.core.config import Config
from src.core.health import HealthManager, HealthStatus


# ============================================================================
# HTTP MOCK FIXTURE HELPERS
# ============================================================================

def make_openrouter_client(
    handler,
    model: str = "openrouter/free",
    allow_paid: bool = False,
    api_key: str = "sk-or-v1-secret-test-key-1234567890",
) -> tuple[OpenRouterProvider, list[httpx.Request]]:
    """Build an OpenRouterProvider backed by an in-memory MockTransport."""
    captured_requests: list[httpx.Request] = []

    def transport_handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return handler(request)

    transport = httpx.MockTransport(transport_handler)
    client = httpx.Client(transport=transport)
    config = ModelConfig(
        provider="openrouter",
        model=model,
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        chat_endpoint="/chat/completions",
        timeout=15.0,
        allow_paid_models=allow_paid,
        site_url="https://astra.local",
        app_name="ASTRA-Desktop",
    )
    provider = OpenRouterProvider(config=config, http_client=client)
    return provider, captured_requests


# ============================================================================
# 1. FACTORY & CONFIGURATION TESTS
# ============================================================================

def test_openrouter_factory_selection():
    """Verify factory resolves 'openrouter' to OpenRouterProvider."""
    config = ModelConfig(
        provider="openrouter",
        model="openrouter/free",
        api_key="sk-or-test-key-12345",
    )
    provider = LLMProviderFactory.create(config)
    assert isinstance(provider, OpenRouterProvider)
    assert provider.model_name == "openrouter/free"
    assert provider.is_free_model(provider.model_name) is True


def test_openrouter_missing_api_key_raises_config_error(monkeypatch):
    """Verify missing API key raises LLMConfigError immediately without silent fallback."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    config = ModelConfig(provider="openrouter", model="openrouter/free", api_key="")
    with pytest.raises(LLMConfigError) as exc_info:
        OpenRouterProvider(config=config)
    assert "OPENROUTER_API_KEY is not configured" in str(exc_info.value)
    assert exc_info.value.error_type == LLMErrorType.INVALID_CONFIGURATION


def test_openrouter_default_free_model():
    """Verify default model is openrouter/free."""
    config = ModelConfig(provider="openrouter", model="", api_key="sk-or-valid-key")
    provider = OpenRouterProvider(config=config)
    assert provider.model_name == "openrouter/free"
    assert provider.is_free_model(provider.model_name) is True


def test_openrouter_cost_protection_free_only():
    """Verify strict cost protection: non-free models rejected when allow_paid_models=False."""
    # 1. Free router allowed
    p1 = OpenRouterProvider(config=ModelConfig(provider="openrouter", model="openrouter/free", api_key="sk-test"))
    assert p1.model_name == "openrouter/free"

    # 2. Free model with :free suffix allowed
    p2 = OpenRouterProvider(
        config=ModelConfig(provider="openrouter", model="meta-llama/llama-3.3-70b-instruct:free", api_key="sk-test")
    )
    assert p2.model_name == "meta-llama/llama-3.3-70b-instruct:free"

    # 3. Paid model without :free rejected by default
    with pytest.raises(LLMConfigError) as exc:
        OpenRouterProvider(
            config=ModelConfig(
                provider="openrouter",
                model="openai/gpt-4o",
                api_key="sk-test",
                allow_paid_models=False,
            )
        )
    assert "not an eligible free model" in str(exc.value)

    # 4. Paid model allowed only when explicitly permitted
    p4 = OpenRouterProvider(
        config=ModelConfig(
            provider="openrouter",
            model="openai/gpt-4o",
            api_key="sk-test",
            allow_paid_models=True,
        )
    )
    assert p4.model_name == "openai/gpt-4o"
    assert p4.allow_paid_models is True


# ============================================================================
# 2. REQUEST HEADERS & PAYLOAD TESTS
# ============================================================================

def test_openrouter_headers_and_payload():
    """Verify request headers, Bearer auth, site/app headers, and OpenAI payload format."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "Bearer sk-or-v1-secret-test-key-1234567890"
        assert request.headers.get("HTTP-Referer") == "https://astra.local"
        assert request.headers.get("X-Title") == "ASTRA-Desktop"
        assert request.headers.get("Content-Type") == "application/json"

        body = json.loads(request.content)
        assert body["model"] == "openrouter/free"
        assert body["stream"] is False
        assert len(body["messages"]) == 2
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][1]["role"] == "user"

        return httpx.Response(
            status_code=200,
            json={
                "id": "gen-123",
                "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "Hello!"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
            },
        )

    provider, requests = make_openrouter_client(handler)
    res = provider.generate("Hi", system_prompt="You are ASTRA.")
    assert res == "Hello!"
    assert len(requests) == 1


# ============================================================================
# 3. RESPONSE PARSING & THINKING SUPPRESSION
# ============================================================================

def test_openrouter_successful_text_generation():
    """Verify successful response parsing and usage metrics."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "id": "gen-456",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "Task completed successfully."},
                    }
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
            },
        )

    provider, _ = make_openrouter_client(handler)
    decision = provider.generate_structured("Do task")
    assert decision.decision_type == DecisionType.RESPONSE
    assert decision.message == "Task completed successfully."
    assert decision.usage.prompt_tokens == 12
    assert decision.usage.completion_tokens == 4
    assert decision.usage.total_tokens == 16
    assert decision.provider == "openrouter"


def test_openrouter_thinking_suppression():
    """Verify inline reasoning <think> blocks are stripped from user output."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "<think>Processing user intent</think>Final clean response.",
                        }
                    }
                ]
            },
        )

    provider, _ = make_openrouter_client(handler)
    res = provider.generate("Test prompt")
    assert "<think>" not in res
    assert "Processing user intent" not in res
    assert res == "Final clean response."


# ============================================================================
# 4. STRUCTURED TOOL CALLS TESTS
# ============================================================================

def test_openrouter_structured_tool_calls():
    """Verify OpenRouter tool calls are normalized into canonical LLMDecision."""
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert "tools" in body
        assert body["tools"][0]["function"]["name"] == "open_application"

        return httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_abc123",
                                    "type": "function",
                                    "function": {
                                        "name": "open_application",
                                        "arguments": json.dumps({"app_name": "calculator"}),
                                    },
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10},
            },
        )

    provider, _ = make_openrouter_client(handler)
    tool_schemas = [
        {
            "name": "open_application",
            "description": "Opens an app",
            "parameters": {"type": "object", "properties": {"app_name": {"type": "string"}}},
        }
    ]
    decision = provider.generate_structured("Open calculator", tool_schemas=tool_schemas)

    assert decision.decision_type == DecisionType.TOOL_CALL
    assert decision.tool_name == "open_application"
    assert decision.arguments == {"app_name": "calculator"}
    assert len(decision.tool_calls) == 1
    assert decision.tool_calls[0]["id"] == "call_abc123"


def test_openrouter_malformed_arguments_handling():
    """Verify non-JSON tool call arguments raise LLMProviderError cleanly."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "call_bad",
                                    "type": "function",
                                    "function": {"name": "search_files", "arguments": "NOT_VALID_JSON{{"},
                                }
                            ],
                        }
                    }
                ]
            },
        )

    provider, _ = make_openrouter_client(handler)
    with pytest.raises(LLMProviderError) as exc:
        provider.generate_structured("Find file")
    assert "non-JSON arguments" in str(exc.value)


def test_openrouter_empty_response_handling():
    """Verify empty response raises LLMProviderError cleanly."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": ""}}]},
        )

    provider, _ = make_openrouter_client(handler)
    with pytest.raises(LLMProviderError) as exc:
        provider.generate_structured("Hello")
    assert "empty response" in str(exc.value)


# ============================================================================
# 5. ERROR CLASSIFICATION & HTTP STATUS TESTS
# ============================================================================

def test_openrouter_unauthorized_error():
    """Verify HTTP 401 maps to non-retryable LLMAuthError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=401,
            json={"error": {"message": "Invalid API Key", "code": 401}},
        )

    provider, _ = make_openrouter_client(handler)
    with pytest.raises(LLMAuthError) as exc:
        provider.generate("Test")
    assert exc.value.error_type == LLMErrorType.AUTH_FAILED
    assert exc.value.retryable is False


def test_openrouter_credit_or_payment_error():
    """Verify HTTP 402 maps to non-retryable LLMQuotaExhaustedError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=402,
            json={"error": {"message": "Insufficient credits to complete request", "code": 402}},
        )

    provider, _ = make_openrouter_client(handler)
    with pytest.raises(LLMQuotaExhaustedError) as exc:
        provider.generate("Test")
    assert exc.value.error_type == LLMErrorType.QUOTA_EXHAUSTED
    assert exc.value.retryable is False


def test_openrouter_rate_limit_and_retry_after():
    """Verify HTTP 429 maps to retryable LLMRateLimitError with Retry-After header."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=429,
            headers={"Retry-After": "4.5"},
            json={"error": {"message": "Rate limit exceeded. Please slow down.", "code": 429}},
        )

    provider, _ = make_openrouter_client(handler)
    with pytest.raises(LLMRateLimitError) as exc:
        provider.generate("Test")
    assert exc.value.error_type == LLMErrorType.RATE_LIMITED
    assert exc.value.retryable is True
    assert exc.value.retry_after == 4.5


def test_openrouter_quota_exhaustion_error():
    """Verify HTTP 429 with quota hints maps to non-retryable LLMQuotaExhaustedError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=429,
            json={"error": {"message": "Daily free tier request limit reached for this model.", "code": 429}},
        )

    provider, _ = make_openrouter_client(handler)
    with pytest.raises(LLMQuotaExhaustedError) as exc:
        provider.generate("Test")
    assert exc.value.error_type == LLMErrorType.QUOTA_EXHAUSTED
    assert exc.value.retryable is False


def test_openrouter_model_not_found():
    """Verify HTTP 404 maps to LLMModelNotFoundError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=404,
            json={"error": {"message": "Model 'openrouter/free' not found.", "code": 404}},
        )

    provider, _ = make_openrouter_client(handler)
    with pytest.raises(LLMModelNotFoundError) as exc:
        provider.generate("Test")
    assert exc.value.error_type == LLMErrorType.MODEL_NOT_FOUND


def test_openrouter_timeout_error():
    """Verify httpx.TimeoutException maps to retryable LLMTimeoutError."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Connection timed out")

    provider, _ = make_openrouter_client(handler)
    with pytest.raises(LLMTimeoutError) as exc:
        provider.generate("Test")
    assert exc.value.error_type == LLMErrorType.TIMEOUT
    assert exc.value.retryable is True


def test_openrouter_network_error():
    """Verify httpx.TransportError maps to retryable LLMNetworkError."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    provider, _ = make_openrouter_client(handler)
    with pytest.raises(LLMNetworkError) as exc:
        provider.generate("Test")
    assert exc.value.error_type == LLMErrorType.NETWORK_ERROR
    assert exc.value.retryable is True


def test_openrouter_5xx_retry_behavior():
    """Verify HTTP 500/502/503 maps to retryable LLMServiceUnavailableError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=503,
            json={"error": {"message": "Upstream model provider temporarily unavailable", "code": 503}},
        )

    provider, _ = make_openrouter_client(handler)
    with pytest.raises(LLMServiceUnavailableError) as exc:
        provider.generate("Test")
    assert exc.value.error_type == LLMErrorType.SERVICE_UNAVAILABLE
    assert exc.value.retryable is True


# ============================================================================
# 6. SECRET REDACTION & LOGGING PROTECTION
# ============================================================================

def test_openrouter_secret_redaction(caplog):
    """Verify API keys are never exposed in logs, repr, or error strings."""
    secret_key = "sk-or-v1-my-ultra-secret-key-99999"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=401,
            json={"error": {"message": f"Auth failed with key {secret_key}"}},
        )

    provider, _ = make_openrouter_client(handler, api_key=secret_key)

    # Repr must not contain key
    assert secret_key not in repr(provider)

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(LLMAuthError) as exc:
            provider.generate("Test")

        # Exception message must be redacted
        assert secret_key not in str(exc.value)

        # Caplog must not contain key
        assert secret_key not in caplog.text


# ============================================================================
# 7. HEALTH CHECK & INTEGRATION TESTS
# ============================================================================

def test_openrouter_health_check():
    """Verify check_health returns valid metadata and is_free flag."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, json={})

    provider, _ = make_openrouter_client(handler)
    health = provider.check_health()
    assert health["status"] == "ok"
    assert health["provider"] == "openrouter"
    assert health["model"] == "openrouter/free"
    assert health["is_free"] is True


def test_openrouter_agent_end_to_end_integration():
    """Verify AstraAgent processes commands through OpenRouterProvider."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "The weather today is clear and sunny."},
                    }
                ]
            },
        )

    provider, _ = make_openrouter_client(handler)
    agent = AstraAgent(llm_provider=provider)

    response, result = agent.process_command("What is the weather?")
    assert "clear and sunny" in response
    assert result.status == ExecutionStatus.SUCCESS


def test_openrouter_no_double_tool_execution_on_failure():
    """Verify that if a tool executes in iteration 1 and the LLM fails in iteration 2,
    the tool is NOT executed again."""
    call_count = {"llm": 0, "tool": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["llm"] += 1
        if call_count["llm"] == 1:
            # Iteration 1: model returns tool call to calculator
            return httpx.Response(
                status_code=200,
                json={
                    "choices": [
                        {
                            "finish_reason": "tool_calls",
                            "message": {
                                "role": "assistant",
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {"name": "open_application", "arguments": "{\"app_name\": \"calculator\"}"},
                                    }
                                ],
                            },
                        }
                    ]
                },
            )
        else:
            # Iteration 2: model crashes with 500 error
            return httpx.Response(status_code=500, json={"error": "Upstream crash"})

    provider, _ = make_openrouter_client(handler)
    agent = AstraAgent(llm_provider=provider)

    with patch.object(agent.executor, "execute", wraps=agent.executor.execute) as mock_exec:
        resp, res = agent.process_command("Open calculator")
        # Tool should be executed exactly once
        assert mock_exec.call_count == 1
        assert res.status == ExecutionStatus.SUCCESS


def test_openrouter_provider_fallback_failover():
    """Verify LLMClient fails over to configured fallback provider on primary failure."""
    def failing_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=429, json={"error": "Daily quota limit reached"})

    primary, _ = make_openrouter_client(failing_handler)

    # Secondary mock provider that succeeds
    mock_fallback = MagicMock()
    mock_fallback.config = ModelConfig(provider="mock-fallback", model="fallback-v1")
    mock_fallback.generate_structured.return_value = LLMDecision(
        decision_type=DecisionType.RESPONSE,
        message="Handled by fallback provider.",
        provider="mock-fallback",
    )

    client = LLMClient(config=primary.config, provider=primary, fallback_provider=mock_fallback)
    decision = client.generate_decision("Hello")

    assert decision.decision_type == DecisionType.RESPONSE
    assert decision.message == "Handled by fallback provider."
    assert "Failover from openrouter" in decision.reason
    mock_fallback.generate_structured.assert_called_once()


# ============================================================================
# 8. OPT-IN LIVE API SMOKE TEST
# ============================================================================

@pytest.mark.integration
def test_real_openrouter_api_if_key_available():
    """
    Opt-in live smoke test against OpenRouter Free API.
    Runs ONLY when OPENROUTER_API_KEY is configured in the environment
    and OPENROUTER_LIVE_TEST is set to 'true'.
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    live_enabled = os.getenv("OPENROUTER_LIVE_TEST", "false").lower() in ("true", "1", "yes")

    if not api_key:
        pytest.skip("OPENROUTER_API_KEY not configured in environment; skipping live test.")
    if not live_enabled:
        pytest.skip("OPENROUTER_LIVE_TEST not enabled; set OPENROUTER_LIVE_TEST=true to run live API test.")

    config = ModelConfig(
        provider="openrouter",
        model="openrouter/free",
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        timeout=30.0,
    )
    provider = OpenRouterProvider(config=config)
    try:
        decision = provider.generate_structured("Say 'ASTRA OK' and nothing else.")
        assert decision.decision_type in (DecisionType.RESPONSE, DecisionType.TOOL_CALL)
        if decision.message:
            assert len(decision.message) > 0
    finally:
        provider.shutdown()
