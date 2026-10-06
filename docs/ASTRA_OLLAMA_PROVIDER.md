# ASTRA — Ollama LLM Provider Integration

This document describes the production-grade Ollama LLM Provider integration in ASTRA.

---

## 1. Architecture Overview

ASTRA supports multiple first-class LLM providers behind a canonical, provider-agnostic interface. The `Agent` interacts exclusively with `LLMClient`, which forwards requests to the configured `LLMProvider`:

```
ASTRA Agent
    │
    ▼
LLMClient (retry / backoff / health tracking / error mapping)
    │
    ▼
LLMProvider (canonical interface: generate, generate_structured, chat)
    ├── MockLLMProvider (development / tests)
    ├── GeminiProvider (Google Gemini API via google-genai SDK)
    └── OllamaProvider (Ollama Cloud / Local via httpx)
            │
            ▼
    POST https://ollama.com/api/chat
    (Authorization: Bearer <OLLAMA_API_KEY>)
            │
            ▼
        gemma4:31b
            │
            ▼
    ASTRA Canonical Response / Tool Call
```

### Key Architectural Principles
- **No Agent Coupling**: `AstraAgent` has no knowledge of Ollama-specific payloads, endpoints, or headers.
- **Single Canonical Tool Flow**: Tools and capabilities registered in ASTRA's `CapabilityRegistry` / `ToolRegistry` are converted into the standard function format expected by Ollama. Responses are normalized back into canonical `LLMDecision(decision_type=TOOL_CALL, tool_name=..., arguments=...)`.
- **Zero Silent Fallback**: If `LLM_PROVIDER=ollama` is configured and credentials or endpoints are invalid, ASTRA fails explicitly with typed `LLMConfigError` or `LLMAuthError`. It never silently falls back to `Mock` in production.
- **Thinking / Reasoning Isolation**: If the model emits internal reasoning traces (`<think>...</think>` or `message.thinking`), ASTRA scrubs them so only final conversational text reaches Agent, TTS, UI, or persistent memory.

---

## 2. Configuration & Environment Variables

Configure Ollama in your local `.env` file (which is git-ignored):

```ini
# Select provider
LLM_PROVIDER=ollama

# Authentication (NEVER commit real keys)
OLLAMA_API_KEY=your_key_here

# Endpoint settings (Cloud API default)
OLLAMA_BASE_URL=https://ollama.com
OLLAMA_CHAT_ENDPOINT=/api/chat

# Model selection (configurable, default: gemma4:31b)
OLLAMA_MODEL=gemma4:31b

# Request timing & bounded retries
OLLAMA_TIMEOUT=60
OLLAMA_MAX_RETRIES=2

# Internal reasoning trace suppression (default: false)
OLLAMA_THINK=false
```

### Cloud vs. Local Ollama Distinction
- **Ollama Cloud (Default)**:
  - Base URL: `https://ollama.com`
  - Chat Endpoint: `/api/chat`
  - Authentication: `Bearer <OLLAMA_API_KEY>` (Required)
- **Local Ollama (Self-Hosted)**:
  - Base URL: `http://localhost:11434`
  - Chat Endpoint: `/api/chat`
  - Authentication: Optional (if loopback host is detected and key is omitted, request proceeds without Authorization header).

---

## 3. API Contract & Request Flow

### Request Construction
The provider issues an HTTP `POST` to `{OLLAMA_BASE_URL}{OLLAMA_CHAT_ENDPOINT}`:

```http
POST https://ollama.com/api/chat HTTP/1.1
Authorization: Bearer <OLLAMA_API_KEY>
Content-Type: application/json
Accept: application/json

{
  "model": "gemma4:31b",
  "messages": [
    {
      "role": "system",
      "content": "You are ASTRA, a helpful voice desktop assistant."
    },
    {
      "role": "user",
      "content": "Open calculator."
    }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "open_application",
        "description": "Open a local desktop application",
        "parameters": {
          "type": "object",
          "properties": {
            "application": {"type": "string"}
          },
          "required": ["application"]
        }
      }
    }
  ],
  "options": {
    "temperature": 0.2,
    "num_predict": 512
  },
  "stream": false,
  "think": false
}
```

### Response Normalization
1. **Conversational Response**:
   ```json
   {
     "model": "gemma4:31b",
     "message": {
       "role": "assistant",
       "content": "Opening Calculator now."
     },
     "done": true,
     "prompt_eval_count": 42,
     "eval_count": 8
   }
   ```
   Normalized to:
   ```python
   LLMDecision(
       decision_type=DecisionType.RESPONSE,
       message="Opening Calculator now.",
       provider="ollama",
       model="gemma4:31b",
       usage=LLMUsage(prompt_tokens=42, completion_tokens=8, total_tokens=50, latency_ms=185.0)
   )
   ```

2. **Tool / Function Calling**:
   ```json
   {
     "model": "gemma4:31b",
     "message": {
       "role": "assistant",
       "content": "",
       "tool_calls": [
         {
           "function": {
             "name": "open_application",
             "arguments": {"application": "calc"}
           }
         }
       ]
     },
     "done": true
   }
   ```
   Normalized to:
   ```python
   LLMDecision(
       decision_type=DecisionType.TOOL_CALL,
       tool_name="open_application",
       arguments={"application": "calc"},
       provider="ollama",
       model="gemma4:31b"
   )
   ```

---

## 4. Security & Privacy Guarantees

1. **Zero Secret Leakage**:
   - `OLLAMA_API_KEY` is loaded exclusively from environment variables / secure configuration.
   - The key is **NEVER** present in `__repr__`, exception text, log files, or frontend payloads.
   - `SecretRedactionFilter` scrubs any bearer tokens or keys from log messages.
2. **Frontend Isolation**:
   - The React UI talks only to `/api/v1/settings` and `/api/v1/health`.
   - Only `llm_provider` and `llm_model` (e.g. `"gemma4:31b"`) are returned; credentials are never exposed to the browser or WebSocket clients.
3. **Execution Safety**:
   - The model output is strictly an advisory decision. Execution is mediated by ASTRA's `ToolExecutor`, `PermissionManager`, and `ToolVerifier`.

---

## 5. Error Taxonomy & Bounded Retries

Ollama HTTP status codes are mapped to typed ASTRA exceptions:

| HTTP Status / Condition | ASTRA Exception | Category | Retryable |
|---|---|---|---|
| `401`, `403` | `LLMAuthError` | `AUTH_FAILED` | No |
| `402`, `429` (quota) | `LLMQuotaExhaustedError` | `QUOTA_EXHAUSTED` | No |
| `429` (rate limit) | `LLMRateLimitError` | `RATE_LIMITED` | Yes (reads `Retry-After`) |
| `404` | `LLMModelNotFoundError` | `MODEL_NOT_FOUND` | No |
| `408`, timeout | `LLMTimeoutError` | `TIMEOUT` | Yes |
| `400`, `413`, `422` | `LLMInvalidRequestError` | `INVALID_REQUEST` | No |
| `500`, `502`, `503`, `504` | `LLMServiceUnavailableError` | `SERVICE_UNAVAILABLE` | Yes |
| Transport / socket fail | `LLMNetworkError` | `NETWORK_ERROR` | Yes |
| Missing configuration | `LLMConfigError` | `INVALID_CONFIGURATION` | No |

**Retry Policy**:
- Bounded retries (default: 2 retries = 3 attempts total) are executed at the `LLMClient` layer using exponential backoff with jitter.
- The provider transport itself performs no internal loops, preventing double-retry storms.

---

## 6. Health Monitoring

The `HealthManager` subsystem tracks LLM operational status:
- **HEALTHY / AVAILABLE**: Successful request outcomes.
- **DEGRADED / RATE_LIMITED**: Transient rate limiting detected.
- **UNAVAILABLE / AUTH_FAILED**: Authentication, quota, or network connectivity failures.

Users can inspect status via `GET /api/v1/health` or `GET /api/v1/settings`.

---

## 7. Testing & Verification

Run the test suite:

```powershell
# Run Ollama mocked unit tests + resilience tests
pytest tests/test_ollama_provider.py tests/test_llm_resilience.py -v

# Run with live Ollama API (if OLLAMA_API_KEY is configured in your local environment)
$env:OLLAMA_API_KEY = "your_key_here"
pytest tests/test_ollama_provider.py -v -k "test_real_ollama_api"
```
