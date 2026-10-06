"""
Tests for Ollama Real LLM Provider Integration.

Covers all 18 Unit Test Scenarios (mocked HTTP via respx / httpx transport):
 1. Successful response
 2. System + user messages
 3. Model configuration
 4. Missing API key (cloud requires key; local allows none)
 5. Unauthorized response (401 / 403 -> LLMAuthError)
 6. Rate limiting (429 -> LLMRateLimitError, retryable)
 7. Quota exhaustion (402 or 429 quota -> LLMQuotaExhaustedError, non-retryable)
 8. Timeout (httpx.TimeoutException / 408 -> LLMTimeoutError, retryable)
 9. Network error (httpx.TransportError -> LLMNetworkError, retryable)
10. 5xx retry (500 / 502 / 503 -> LLMServiceUnavailableError, retryable by LLMClient)
11. Invalid model (404 -> LLMModelNotFoundError, non-retryable)
12. Malformed response (non-JSON, missing fields -> LLMProviderError)
13. Response normalization (Ollama response -> canonical LLMDecision)
14. Tool call normalization (Ollama tool_calls -> canonical schema)
15. Secret redaction (API key never in logs, repr, or exception messages)
16. Factory selection (LLM_PROVIDER=ollama -> OllamaProvider)
17. No Mock fallback (Production fails clearly, never downgrades to Mock)
18. Health updates (HealthManager reflects Ollama state)

Plus:
- End-to-end smoke path (User command -> AstraAgent -> LLMClient -> OllamaProvider -> Gemma 4 -> Response)
- Real API integration test (skips gracefully if OLLAMA_API_KEY is not set)
"""

import json
import logging
import os
from typing import Any
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
from src.brain.llm.ollama_provider import OllamaProvider
from src.core.config import Config
from src.core.health import HealthManager, HealthStatus


# ============================================================================
# HTTP MOCK FIXTURE HELPERS
# ============================================================================

def make_ollama_client(handler) -> tuple[OllamaProvider, list[httpx.Request]]:
    """Build an OllamaProvider backed by an in-memory MockTransport."""
    captured_requests: list[httpx.Request] = []

    def transport_handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return handler(request)

    transport = httpx.MockTransport(transport_handler)
    client = httpx.Client(transport=transport)
    config = ModelConfig(
        provider="ollama",
        model="gemma4:31b",
        api_key="secret-ollama-key-xyz-12345",
        base_url="https://ollama.com",
        chat_endpoint="/api/chat",
        timeout=15.0,
    )
    provider = OllamaProvider(config=config, http_client=client)
    return provider, captured_requests


# ============================================================================
# 1. SUCCESSFUL RESPONSE
# ============================================================================

def test_ollama_successful_text_generation():
    """Provider sends proper Bearer auth and payload, returning normalized text."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://ollama.com/api/chat"
        assert request.headers["Authorization"] == "Bearer secret-ollama-key-xyz-12345"
        assert request.headers["Content-Type"] == "application/json"
        body = json.loads(request.content)
        assert body["model"] == "gemma4:31b"
        assert body["stream"] is False

        return httpx.Response(
            200,
            json={
                "model": "gemma4:31b",
                "message": {"role": "assistant", "content": "Hello! I am ASTRA powered by Gemma 4."},
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 14,
                "eval_count": 12,
            },
        )

    provider, reqs = make_ollama_client(handler)
    result = provider.generate("Hi ASTRA", system_prompt="You are ASTRA.")

    assert result == "Hello! I am ASTRA powered by Gemma 4."
    assert len(reqs) == 1


# ============================================================================
# 2. SYSTEM + USER + CONVERSATION HISTORY MESSAGES
# ============================================================================

def test_ollama_system_and_history_messages():
    """Verify system, user, assistant, and tool messages are formatted without concatenation."""
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        msgs = body["messages"]
        assert len(msgs) == 3
        assert msgs[0] == {"role": "system", "content": "You are ASTRA desktop assistant."}
        assert msgs[1] == {"role": "user", "content": "What is the time?"}
        assert msgs[2] == {"role": "assistant", "content": "It is 2:00 PM."}
        return httpx.Response(
            200,
            json={
                "model": "gemma4:31b",
                "message": {"role": "assistant", "content": "Understood."},
                "done": True,
            },
        )

    provider, _ = make_ollama_client(handler)
    history = [
        LLMMessage(role="system", content="You are ASTRA desktop assistant."),
        LLMMessage(role="user", content="What is the time?"),
        LLMMessage(role="assistant", content="It is 2:00 PM."),
    ]
    decision = provider.chat(history)
    assert decision.decision_type == DecisionType.RESPONSE
    assert decision.message == "Understood."


# ============================================================================
# 3. MODEL CONFIGURATION OVERRIDE
# ============================================================================

def test_ollama_custom_model_configuration():
    """Custom models (e.g. gemma4:12b, custom local) are respected and not hardcoded."""
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "gemma4:12b"
        return httpx.Response(
            200,
            json={
                "model": "gemma4:12b",
                "message": {"role": "assistant", "content": "Running 12b model."},
                "done": True,
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    cfg = ModelConfig(
        provider="ollama",
        model="gemma4:12b",
        api_key="valid-test-key-12345",
    )
    provider = OllamaProvider(config=cfg, http_client=client)
    decision = provider.generate_structured("test")
    assert decision.model == "gemma4:12b"
    assert decision.message == "Running 12b model."


# ============================================================================
# 4. MISSING API KEY
# ============================================================================

def test_ollama_missing_api_key_raises_config_error(monkeypatch):
    """Cloud Ollama requires an API key. Missing key raises clear LLMConfigError."""
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    cfg = ModelConfig(provider="ollama", api_key="", base_url="https://ollama.com")
    with pytest.raises(LLMConfigError) as excinfo:
        OllamaProvider(config=cfg)

    assert "Ollama API key is missing" in str(excinfo.value)
    assert excinfo.value.error_type == LLMErrorType.INVALID_CONFIGURATION


def test_ollama_local_base_url_allows_no_api_key():
    """When configured for local Ollama (e.g. localhost:11434), missing key does not fail."""
    cfg = ModelConfig(
        provider="ollama",
        api_key="",
        base_url="http://localhost:11434",
    )
    provider = OllamaProvider(config=cfg, http_client=httpx.Client())
    assert provider.is_local is True
    assert provider.chat_url == "http://localhost:11434/api/chat"
    assert "Authorization" not in provider._headers()


# ============================================================================
# 5. UNAUTHORIZED RESPONSE (401 / 403)
# ============================================================================

def test_ollama_unauthorized_error():
    """HTTP 401 maps to non-retryable LLMAuthError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid api key provided"})

    provider, _ = make_ollama_client(handler)
    with pytest.raises(LLMAuthError) as excinfo:
        provider.generate("test")

    assert excinfo.value.error_type == LLMErrorType.AUTH_FAILED
    assert excinfo.value.status_code == 401
    assert not excinfo.value.retryable


# ============================================================================
# 6. RATE LIMITING (429)
# ============================================================================

def test_ollama_rate_limiting_error():
    """HTTP 429 maps to retryable LLMRateLimitError with retry_after parsed."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"Retry-After": "4.5"},
            json={"error": "rate limit exceeded, please slow down"},
        )

    provider, _ = make_ollama_client(handler)
    with pytest.raises(LLMRateLimitError) as excinfo:
        provider.generate("test")

    assert excinfo.value.error_type == LLMErrorType.RATE_LIMITED
    assert excinfo.value.retryable is True
    assert excinfo.value.retry_after == 4.5


# ============================================================================
# 7. QUOTA EXHAUSTION
# ============================================================================

def test_ollama_quota_exhausted_error():
    """HTTP 402 or 429 with quota keywords maps to non-retryable LLMQuotaExhaustedError."""
    def handler_402(request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"error": "Usage quota exceeded. Please upgrade subscription."})

    provider, _ = make_ollama_client(handler_402)
    with pytest.raises(LLMQuotaExhaustedError) as excinfo:
        provider.generate("test")

    assert excinfo.value.error_type == LLMErrorType.QUOTA_EXHAUSTED
    assert excinfo.value.retryable is False

    def handler_429_quota(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "daily request credits limit reached"})

    provider2, _ = make_ollama_client(handler_429_quota)
    with pytest.raises(LLMQuotaExhaustedError) as excinfo2:
        provider2.generate("test")
    assert excinfo2.value.error_type == LLMErrorType.QUOTA_EXHAUSTED
    assert not excinfo2.value.retryable


# ============================================================================
# 8. TIMEOUT ERROR
# ============================================================================

def test_ollama_timeout_error():
    """httpx.TimeoutException maps to retryable LLMTimeoutError."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Request timed out", request=request)

    provider, _ = make_ollama_client(handler)
    with pytest.raises(LLMTimeoutError) as excinfo:
        provider.generate("test")

    assert excinfo.value.error_type == LLMErrorType.TIMEOUT
    assert excinfo.value.retryable is True


# ============================================================================
# 9. NETWORK TRANSPORT ERROR
# ============================================================================

def test_ollama_network_error():
    """httpx.ConnectError maps to retryable LLMNetworkError."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused to ollama.com", request=request)

    provider, _ = make_ollama_client(handler)
    with pytest.raises(LLMNetworkError) as excinfo:
        provider.generate("test")

    assert excinfo.value.error_type == LLMErrorType.NETWORK_ERROR
    assert excinfo.value.retryable is True


# ============================================================================
# 10. 5XX SERVICE UNAVAILABLE & RETRY VIA LLMCLIENT
# ============================================================================

def test_ollama_5xx_retry_behavior():
    """5xx errors map to LLMServiceUnavailableError and are retried by LLMClient."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, json={"error": "Ollama service temporarily overloaded"})
        return httpx.Response(
            200,
            json={
                "model": "gemma4:31b",
                "message": {"role": "assistant", "content": "Recovered on attempt 2"},
                "done": True,
            },
        )

    provider, _ = make_ollama_client(handler)
    client = LLMClient(
        config=ModelConfig(provider="ollama", retry_count=2, initial_backoff=0.01, max_backoff=0.05),
        provider=provider,
    )
    decision = client.generate_decision("Hello")
    assert decision.decision_type == DecisionType.RESPONSE
    assert decision.message == "Recovered on attempt 2"
    assert calls == 2


# ============================================================================
# 11. INVALID MODEL (404)
# ============================================================================

def test_ollama_model_not_found():
    """HTTP 404 maps to non-retryable LLMModelNotFoundError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model 'nonexistent-model' not found"})

    provider, _ = make_ollama_client(handler)
    with pytest.raises(LLMModelNotFoundError) as excinfo:
        provider.generate("test")

    assert excinfo.value.error_type == LLMErrorType.MODEL_NOT_FOUND
    assert excinfo.value.status_code == 404
    assert not excinfo.value.retryable


# ============================================================================
# 12. MALFORMED RESPONSE
# ============================================================================

def test_ollama_malformed_response():
    """Non-JSON or missing message object triggers LLMProviderError."""
    def handler_non_json(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>502 Bad Gateway Cloudflare</html>")

    provider, _ = make_ollama_client(handler_non_json)
    with pytest.raises(LLMProviderError) as excinfo:
        provider.generate("test")
    assert "malformed" in str(excinfo.value).lower()

    def handler_missing_message(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"model": "gemma4:31b", "done": True})

    provider2, _ = make_ollama_client(handler_missing_message)
    with pytest.raises(LLMProviderError) as excinfo2:
        provider2.generate("test")
    assert "missing the 'message' object" in str(excinfo2.value).lower()


# ============================================================================
# 13. RESPONSE NORMALIZATION & THINKING SUPPRESSION
# ============================================================================

def test_ollama_response_normalization_and_thinking_suppression():
    """Reasoning traces in <think> tags or message.thinking are stripped from user output."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "gemma4:31b",
                "message": {
                    "role": "assistant",
                    "thinking": "INTERNAL REASONING TRACE THAT MUST NOT BE SHOWN",
                    "content": "<think>Deliberating user request step 1</think>Here is the final answer for the user.",
                },
                "done": True,
                "prompt_eval_count": 20,
                "eval_count": 15,
            },
        )

    provider, _ = make_ollama_client(handler)
    decision = provider.generate_structured("Question")

    assert decision.decision_type == DecisionType.RESPONSE
    assert decision.message == "Here is the final answer for the user."
    assert "INTERNAL REASONING" not in decision.message
    assert "<think>" not in decision.message
    assert decision.usage.prompt_tokens == 20
    assert decision.usage.completion_tokens == 15
    assert decision.provider == "ollama"
    assert decision.model == "gemma4:31b"


# ============================================================================
# 14. TOOL CALL NORMALIZATION
# ============================================================================

def test_ollama_tool_call_normalization():
    """Ollama tool_calls map cleanly into ASTRA canonical format."""
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        # Verify tool schemas passed
        assert len(body["tools"]) == 1
        assert body["tools"][0]["function"]["name"] == "open_application"

        return httpx.Response(
            200,
            json={
                "model": "gemma4:31b",
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "open_application",
                                "arguments": {"application": "chrome"},
                            }
                        }
                    ],
                },
                "done": True,
            },
        )

    provider, _ = make_ollama_client(handler)
    schemas = [
        {
            "name": "open_application",
            "description": "Open a local desktop application",
            "parameters": {
                "type": "object",
                "properties": {"application": {"type": "string"}},
                "required": ["application"],
            },
        }
    ]
    decision = provider.generate_structured("Open chrome", tool_schemas=schemas)

    assert decision.decision_type == DecisionType.TOOL_CALL
    assert decision.tool_name == "open_application"
    assert decision.arguments == {"application": "chrome"}
    assert decision.provider == "ollama"
    assert decision.model == "gemma4:31b"


# ============================================================================
# 15. SECRET REDACTION
# ============================================================================

def test_ollama_api_key_redaction_in_repr_and_errors():
    """API key is never printed in repr, string representations, or exception messages."""
    raw_secret = "secret-super-sensitive-ollama-token-998877"
    cfg = ModelConfig(
        provider="ollama",
        api_key=raw_secret,
        base_url="https://ollama.com",
    )
    provider = OllamaProvider(config=cfg, http_client=httpx.Client())

    # repr test
    repr_str = repr(provider)
    assert raw_secret not in repr_str
    assert "secret" not in repr_str

    # config repr test
    assert raw_secret not in repr(cfg)

    # scrub test in errors
    err = provider.classify_http_error(
        httpx.Response(400, text=f"Error occurred with token {raw_secret} on endpoint")
    )
    assert raw_secret not in str(err)
    assert "[REDACTED]" in str(err)


# ============================================================================
# 16. FACTORY SELECTION
# ============================================================================

def test_ollama_factory_selection():
    """LLMProviderFactory.create instantiates OllamaProvider when provider='ollama'."""
    cfg = ModelConfig(
        provider="ollama",
        model="gemma4:31b",
        api_key="valid-dummy-key-12345",
    )
    instance = LLMProviderFactory.create(cfg)
    assert isinstance(instance, OllamaProvider)
    assert instance.model_name == "gemma4:31b"
    assert instance.chat_url == "https://ollama.com/api/chat"


# ============================================================================
# 17. NO MOCK FALLBACK IN PRODUCTION
# ============================================================================

def test_ollama_no_mock_fallback_on_invalid_config(monkeypatch):
    """When LLM_PROVIDER=ollama and configuration is invalid, ASTRA must fail clearly, NEVER silently using Mock."""
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    app_cfg = Config()
    app_cfg.llm_provider = "ollama"
    app_cfg.ollama_api_key = ""

    model_config = ModelConfig.from_app_config(app_cfg)
    with pytest.raises(LLMConfigError) as excinfo:
        LLMProviderFactory.create(model_config)

    assert "Ollama API key is missing" in str(excinfo.value)
    # Ensure it didn't return a MockLLMProvider
    assert excinfo.value.provider == "ollama"


# ============================================================================
# 18. HEALTH UPDATES
# ============================================================================

def test_ollama_health_manager_updates():
    """HealthManager reflects Ollama AVAILABLE on success and UNAVAILABLE / DEGRADED on failures."""
    health_mgr = HealthManager()

    # Success scenario
    def ok_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"model": "gemma4:31b", "message": {"role": "assistant", "content": "OK"}})

    provider, _ = make_ollama_client(ok_handler)
    client = LLMClient(
        config=ModelConfig(provider="ollama", api_key="test-key-12345"),
        provider=provider,
        health_manager=health_mgr,
    )
    client.generate_decision("Hi")
    status = health_mgr.get_status("LLM")
    assert status.status == HealthStatus.HEALTHY
    assert "Ollama" in status.message

    # Rate limited scenario
    def rate_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "Too many requests"})

    provider2, _ = make_ollama_client(rate_handler)
    client2 = LLMClient(
        config=ModelConfig(provider="ollama", retry_count=1, api_key="test-key-12345"),
        provider=provider2,
        health_manager=health_mgr,
    )
    client2.generate_decision("Hi")
    status2 = health_mgr.get_status("LLM")
    assert status2.status == HealthStatus.DEGRADED
    assert "Rate Limited" in status2.message

    # Auth failed scenario
    def auth_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    provider3, _ = make_ollama_client(auth_handler)
    client3 = LLMClient(
        config=ModelConfig(provider="ollama", api_key="test-key-12345"),
        provider=provider3,
        health_manager=health_mgr,
    )
    client3.generate_decision("Hi")
    status3 = health_mgr.get_status("LLM")
    assert status3.status == HealthStatus.UNAVAILABLE
    assert "Authentication Failed" in status3.message


# ============================================================================
# 25. END-TO-END SMOKE TEST WITH ASTRA AGENT
# ============================================================================

def test_ollama_agent_end_to_end_smoke():
    """End-to-end smoke path: User command -> AstraAgent -> LLMClient -> OllamaProvider -> Gemma 4 -> Astra response."""
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "gemma4:31b"
        return httpx.Response(
            200,
            json={
                "model": "gemma4:31b",
                "message": {
                    "role": "assistant",
                    "content": "Good day! All systems operational under Gemma 4.",
                },
                "done": True,
                "prompt_eval_count": 50,
                "eval_count": 15,
            },
        )

    provider, reqs = make_ollama_client(handler)

    app_config = Config()
    app_config.llm_provider = "ollama"
    app_config.ollama_model = "gemma4:31b"

    agent = AstraAgent(
        config=app_config,
        llm_provider=provider,
    )

    response_text, tool_result = agent.process_command("Report status")
    assert response_text == "Good day! All systems operational under Gemma 4."
    assert len(reqs) >= 1

    # Verify safe provider status reported
    status_report = agent.llm_client.get_provider_status()
    assert status_report["provider"] == "Ollama"
    assert status_report["model"] == "gemma4:31b"
    assert status_report["state"] == ProviderHealthState.AVAILABLE.value


# ============================================================================
# 23. DIRECT PROVIDER INTEGRATION TEST (RUNS ONLY IF OLLAMA_API_KEY SET)
# ============================================================================

@pytest.mark.integration
def test_real_ollama_api_if_key_available():
    """Live integration test against https://ollama.com/api/chat.

    Gracefully skipped when OLLAMA_API_KEY is not in the environment.
    Never prints or logs the credential.
    """
    api_key = os.getenv("OLLAMA_API_KEY", "").strip()
    if not api_key:
        pytest.skip("OLLAMA_API_KEY not configured in environment; skipping live API test.")

    model = os.getenv("OLLAMA_MODEL", "gemma4:31b").strip()
    base_url = os.getenv("OLLAMA_BASE_URL", "https://ollama.com").strip()
    chat_endpoint = os.getenv("OLLAMA_CHAT_ENDPOINT", "/api/chat").strip()

    cfg = ModelConfig(
        provider="ollama",
        model=model,
        api_key=api_key,
        base_url=base_url,
        chat_endpoint=chat_endpoint,
        timeout=30.0,
    )
    provider = OllamaProvider(config=cfg)
    decision = provider.generate_structured("Say 'OK' and nothing else.")

    assert decision.decision_type in (DecisionType.RESPONSE, DecisionType.TOOL_CALL)
    assert decision.provider == "ollama"
    assert decision.model == model
    assert decision.message is not None
