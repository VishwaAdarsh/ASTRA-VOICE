# ASTRA V2 — LLM Provider Architecture

**Phase:** V2-02  
**Status:** Canonical  
**Date:** 2026-09-16  

---

## 1. Overview & Architecture

ASTRA V2 decouples conversational and agentic intelligence into a modular, provider-independent LLM subsystem (`src/brain/llm/`). The architecture enforces strict boundaries between:
1. **Model Configuration:** Parameter containers (`ModelConfig`) specifying provider name, model identification, generation hyperparameters, and backoff settings.
2. **Provider Implementations:** Adapter classes (`GeminiProvider`, `MockLLMProvider`) implementing the common `LLMProvider` contract.
3. **Provider Factory:** Authoritative registry (`LLMProviderFactory`) that instantiates providers strictly on explicit configuration.
4. **Resilient Client Engine:** High-level execution orchestrator (`LLMClient`) providing bounded exponential backoff, health tracking, quota short-circuiting, and typed exception isolation.
5. **Subsystem Health Monitoring:** Real-time operational diagnostics via `HealthManager` (`HEALTHY`, `DEGRADED`, `UNAVAILABLE`).

```
  ┌─────────────────────────────────────────────────────────┐
  │                       AstraAgent                        │
  └────────────────────────────┬────────────────────────────┘
                               │
                               ▼
  ┌─────────────────────────────────────────────────────────┐
  │                        LLMClient                        │
  │  - Bounded exponential backoff + jitter                 │
  │  - HealthManager telemetry updates                      │
  │  - Typed error classification & user-friendly messaging  │
  └───────────┬─────────────────────────────────┬───────────┘
              │                                 │
              ▼                                 ▼
   [LLMProviderFactory]                [HealthManager]
              │                         - HEALTHY
       ┌──────┴──────┐                  - DEGRADED (Rate Limit)
       ▼             ▼                  - UNAVAILABLE (Quota/Auth)
┌──────────────┐ ┌──────────────┐
│GeminiProvider│ │MockLLMProvider│
│(Production)  │ │(Testing/Dev) │
└──────────────┘ └──────────────┘
```

---

## 2. Prohibition of Silent Mock Fallback (ADR-003)

A core tenet of ASTRA V2 is **zero silent degradation to mock implementations in production**:
- If `GeminiProvider` encounters authentication failure, network partition, or quota exhaustion, it **MUST NEVER** fall back to `MockLLMProvider`.
- Silent fallback masks configuration bugs and misleads users into believing real AI reasoning took place when canned responses were returned.
- `MockLLMProvider` is restricted strictly to offline test environments and explicit test configurations (`provider="mock"`).
- Production failures trigger explicit, typed errors that update the system's `HealthManager` and allow graceful degradation at the rule-based intent fallback layer (e.g., local emergency stop, local clock lookup).

---

## 3. Explicit Error Taxonomy

All LLM-related errors inherit from `LLMProviderError` and are tagged with an explicit `LLMErrorType` enum (`src/brain/llm/errors.py`):

| Exception Class | Error Type | HTTP / Cause | Retryable? | Health State | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `LLMAuthError` | `AUTH_FAILED` | 401, 403 | **False** | `UNAVAILABLE` | Invalid, expired, or missing API key. Retries aborted immediately. |
| `LLMConfigError` | `INVALID_CONFIGURATION` | Client init / setup | **False** | `UNAVAILABLE` | Invalid model parameters, missing key configuration, or unknown provider. |
| `LLMQuotaExhaustedError` | `QUOTA_EXHAUSTED` | 429 (`limit: 20`, daily quota) | **False** | `UNAVAILABLE` | Daily Free Tier quota exhausted (`GenerateRequestsPerDayPerProjectPerModel`). Retries aborted immediately. |
| `LLMRateLimitError` | `RATE_LIMITED` | 429 (Per-minute RPM/TPM) | **True** | `DEGRADED` | Transient burst limit reached. Retried with exponential backoff or provider `retry_after`. |
| `LLMServiceUnavailableError` | `SERVICE_UNAVAILABLE` | 500, 502, 503, 504 | **True** | `UNAVAILABLE` | Upstream provider transient outage or server error. Retried with backoff. |
| `LLMTimeoutError` | `TIMEOUT` | Client / Network timeout | **True** | `UNAVAILABLE` | Upstream request timed out. Retried with backoff. |
| `LLMNetworkError` | `NETWORK_ERROR` | Connection reset / DNS | **True** | `UNAVAILABLE` | Transient transport connection error. Retried with backoff. |
| `LLMInvalidRequestError` | `INVALID_REQUEST` | 400 Bad Request | **False** | `UNAVAILABLE` | Malformed payload or prompt syntax error. Retries aborted immediately. |
| `LLMContentPolicyError` | `CONTENT_POLICY_ERROR` | Safety block / Harm | **False** | `UNAVAILABLE` | Prompt or output flagged by safety filter. Retries aborted immediately. |
| `LLMModelNotFoundError` | `MODEL_NOT_FOUND` | 404 Not Found | **False** | `UNAVAILABLE` | Configured model identifier does not exist on provider. |

---

## 4. Exponential Backoff & Retry Strategy

The `LLMClient` executes requests with bounded retry logic governed by `ModelConfig`:
- **Retry Count (`retry_count`):** Default `2` retries (total 3 attempts).
- **Initial Backoff (`initial_backoff`):** Default `1.0s`.
- **Max Backoff (`max_backoff`):** Default `30.0s`.
- **Backoff Factor (`backoff_factor`):** Default `2.0`.
- **Jitter:** Uniform random jitter up to 10% of interval is added to avoid thundering herds.
- **Provider Retry-After Hint:** If the upstream provider returns an explicit `retry_after` duration, the client honors that duration up to `max_backoff`.
- **Immediate Abort on Non-Retryable Errors:** If `retryable == False`, the client breaks the loop on attempt 1 without unnecessary delays.

```python
# Bounded Backoff Calculation:
if retry_after is not None and retry_after > 0:
    backoff = min(retry_after, self.config.max_backoff)
else:
    backoff = min(
        self.config.initial_backoff * (self.config.backoff_factor ** (attempt - 1)),
        self.config.max_backoff,
    )
sleep_sec = min(backoff + random.uniform(0, 0.1 * backoff), self.config.max_backoff)
```

---

## 5. Subsystem Health Diagnostics

`HealthManager` tracks the operational status of the `LLM` subsystem:
- **`HealthStatus.HEALTHY`:** Successful structured or raw generation turn. Subsystem is fully operational.
- **`HealthStatus.DEGRADED`:** Transient rate limiting encountered (`RATE_LIMITED`). Requests are retried, but responsiveness may be delayed.
- **`HealthStatus.UNAVAILABLE`:** Fatal authentication, quota exhaustion, configuration, or repeated service errors occurred.

The REST and WebSocket endpoints expose these diagnostics via `/api/health` and system status broadcasts.

---

## 6. Provider Implementation Details

### Google Gemini (`GeminiProvider`)
- **SDK:** Official Google GenAI SDK (`google-genai`, package `google.genai`).
- **Default Model:** `gemini-3.6-flash`.
- **Capabilities:** `{"text", "structured", "tools"}`.
- **Function Calling:** Translates ASTRA tool definitions (`ToolRegistry`) into Gemini `types.FunctionDeclaration` with schema caching for minimal overhead.
- **Security:** API key read securely from environment (`LLM_API_KEY`, `ASTRA_API_KEY`, `GEMINI_API_KEY`) or config. API keys are never logged.

### Mock Provider (`MockLLMProvider`)
- **Capabilities:** `{"text", "structured"}`.
- **Purpose:** Fast, offline, deterministic unit and integration test execution.
- **Scope:** Pattern matches test commands (Phase 1-8 tools, memory, vision, applications) without network dependency.

### Deferred Providers (Phase V2-20)
- Providers such as `OpenAI`, `Anthropic`, and `Ollama` are explicitly deferred to Phase V2-20 (Multi-Provider Dynamic Router). Requesting them in `LLMProviderFactory` immediately raises `NotImplementedError`.

---

## 7. Configuration Reference

Configuration options in `ModelConfig` and `.env`:

| Setting | Default | Description |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | `gemini` | Target provider (`gemini` or `mock`). |
| `LLM_MODEL` | `gemini-3.6-flash` | Gemini model name. |
| `LLM_API_KEY` | *(secret)* | Provider API Key (never logged or committed). |
| `LLM_TEMPERATURE` | `0.2` | Generation temperature. |
| `LLM_MAX_OUTPUT_TOKENS` | `512` | Token limit for response/tool calls. |
| `LLM_TIMEOUT` | `10.0` | Per-request network timeout (seconds). |
| `LLM_RETRY_COUNT` | `2` | Number of retries for transient errors. |
| `LLM_INITIAL_BACKOFF` | `1.0` | Initial exponential backoff delay (seconds). |
| `LLM_MAX_BACKOFF` | `30.0` | Maximum capped backoff delay (seconds). |
