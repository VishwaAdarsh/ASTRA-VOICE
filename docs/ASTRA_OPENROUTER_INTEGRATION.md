# ASTRA — OpenRouter Free LLM Provider Integration

This document outlines the architecture, configuration, cost protection, and operational procedures for the OpenRouter LLM Provider integration in ASTRA.

---

## 1. Overview & Free-Model Architecture

ASTRA features a pluggable, fail-safe LLM provider architecture designed to ensure zero downtime and strict cost guardrails. The **OpenRouter Provider** (`OpenRouterProvider`) integrates OpenRouter's OpenAI-compatible Chat Completions API into ASTRA as a first-class LLM engine, configured by default to use **100% free models**.

### Core Architecture Pipeline

```text
USER SPEAKS (or types in Web UI)
    ↓
Microphone Capture / Speech Recognition (STT)
    ↓
Event Bus (`AstraEventType.USER_SPEECH_RECOGNIZED`)
    ↓
AstraAgent Orchestrator
    ↓
LLMClient (Resilience, Retry, Failover)
    ↓
OpenRouterProvider (HTTP Bearer Auth, OpenAI-compatible JSON schema)
    ↓
POST https://openrouter.ai/api/v1/chat/completions
    ↓
Model: openrouter/free (Auto-routed across verified free providers)
    ↓
Response Parsing (Decision, Structured Tool Calls, <think> block stripping)
    ↓
Capability Registry / Tool Executor / Tool Verifier (Windows Automation)
    ↓
ElevenLabs Voice Engine (TTS) → Audio Speaker
    ↓
ASTRA TALKS BACK TO USER
```

---

## 2. Step-by-Step: Creating an OpenRouter Account & API Key

1. Navigate to [https://openrouter.ai](https://openrouter.ai).
2. Sign in using your GitHub or Google account (or email).
3. Open the **Keys** section at [https://openrouter.ai/keys](https://openrouter.ai/keys).
4. Click **Create Key**.
5. Give your key a descriptive name (e.g., `astra-desktop-free`).
6. Set the **Credit limit** to `0` or leave it empty to ensure no unexpected charges occur.
7. Copy the generated key (starts with `sk-or-v1-...`).
8. Add it to your `.env` file or environment variables as `OPENROUTER_API_KEY`.

> [!WARNING]
> **Credential Security**: Never commit your API key to Git, paste it in public chat, or write it into code. ASTRA automatically scrubs API keys and Bearer tokens from all logs, error messages, and debug output.

---

## 3. Environment Variables Reference

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `LLM_PROVIDER` | string | `ollama` | Active provider: `openrouter`, `ollama`, `gemini`, or `mock`. |
| `OPENROUTER_API_KEY` | string | `""` | OpenRouter API Key (`sk-or-v1-...`). Required when `openrouter` is active. |
| `OPENROUTER_MODEL` | string | `openrouter/free` | Model identifier. Must end in `:free` or be `openrouter/free`. |
| `OPENROUTER_BASE_URL` | string | `https://openrouter.ai/api/v1` | OpenRouter API base endpoint URL. |
| `OPENROUTER_CHAT_ENDPOINT`| string | `/chat/completions` | Chat completions path. |
| `OPENROUTER_TIMEOUT` | float | `60.0` | HTTP request timeout in seconds. |
| `OPENROUTER_MAX_RETRIES` | int | `3` | Maximum retry attempts on retryable errors (429, 5xx, network). |
| `OPENROUTER_SITE_URL` | string | `https://github.com/astra-voice`| Sent in `HTTP-Referer` header for OpenRouter app rankings. |
| `OPENROUTER_APP_NAME` | string | `ASTRA Voice Assistant` | Sent in `X-Title` header for OpenRouter dashboard. |
| `OPENROUTER_ALLOW_PAID_MODELS` | bool | `false` | Strict safety lock. Must be `true` to use paid models. |
| `LLM_FALLBACK_PROVIDER` | string | `""` | Optional fallback provider on unrecoverable errors (e.g. `ollama`). |

---

## 4. Supported Free Models & Routing Behavior

By default, ASTRA uses `openrouter/free`. This is OpenRouter's official meta-router that dynamically routes prompts to the best available free model with zero rate-limit wait times.

### Recommended Free Models
- `openrouter/free` *(Default — dynamically routes to available free models)*
- `meta-llama/llama-3.3-70b-instruct:free`
- `meta-llama/llama-3.1-8b-instruct:free`
- `google/gemini-2.0-flash-exp:free`
- `google/gemma-2-9b-it:free`
- `mistralai/mistral-small-24b-instruct-2501:free`
- `deepseek/deepseek-r1:free`
- `qwen/qwen-2.5-72b-instruct:free`

Any model ending with the `:free` suffix is recognized as a valid free model.

---

## 5. Configuration Examples

### A. Primary: OpenRouter Free (No Fallback)
```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENROUTER_MODEL=openrouter/free
OPENROUTER_ALLOW_PAID_MODELS=false
```

### B. Primary: OpenRouter Free with Ollama Cloud Fallback
```env
LLM_PROVIDER=openrouter
LLM_FALLBACK_PROVIDER=ollama
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENROUTER_MODEL=openrouter/free

# Fallback Ollama Cloud credentials
OLLAMA_API_KEY=your_ollama_api_key_here
OLLAMA_MODEL=gemma4:31b
```

### C. Primary: Ollama Cloud with OpenRouter Free Fallback
```env
LLM_PROVIDER=ollama
LLM_FALLBACK_PROVIDER=openrouter
OLLAMA_API_KEY=your_ollama_api_key_here
OLLAMA_MODEL=gemma4:31b

# Fallback OpenRouter credentials
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENROUTER_MODEL=openrouter/free
```

---

## 6. Switching Guide

Switching between LLM providers in ASTRA requires **zero code changes** — only setting the `LLM_PROVIDER` environment variable:

### To switch to OpenRouter:
1. Update `.env`:
   ```env
   LLM_PROVIDER=openrouter
   OPENROUTER_API_KEY=sk-or-v1-...
   ```
2. Restart ASTRA:
   ```powershell
   python main.py
   ```

### To switch back to Ollama Cloud:
1. Update `.env`:
   ```env
   LLM_PROVIDER=ollama
   OLLAMA_API_KEY=...
   ```
2. Restart ASTRA:
   ```powershell
   python main.py
   ```

---

## 7. Strict Cost Protection & Safety Locks

To protect users from unintended credit consumption or billing surprises:

1. **Model Name Validation**:
   `OpenRouterProvider` checks `model_name` at construction time. If the model name is neither `openrouter/free` nor ends with `:free`, initialization immediately fails closed with `LLMConfigError`.
2. **Paid Models Lock**:
   Paid models cannot be used unless `OPENROUTER_ALLOW_PAID_MODELS=true` is explicitly set in configuration.
3. **No Automatic Stripping**:
   During retries or network errors, the `:free` suffix is **never** stripped or replaced with a paid equivalent.
4. **No Double Tool Execution**:
   If an agent step successfully executes a desktop control tool, and the subsequent LLM call to synthesize the spoken response encounters a failure or rate limit, ASTRA prevents re-executing the tool and cleanly delivers the executed result to the user.

---

## 8. Error Handling & Resilience

All OpenRouter HTTP responses are mapped directly into ASTRA's unified exception hierarchy:

| HTTP Status / Condition | ASTRA Exception | Retryable? | Behavior |
| :--- | :--- | :--- | :--- |
| **401 / 403** | `LLMAuthError` | No | Fail closed, alert user to check `OPENROUTER_API_KEY`. |
| **402 / Quota Exceeded** | `LLMQuotaExhaustedError` | No | Fail immediately or switch to fallback provider. |
| **429 Rate Limit** | `LLMRateLimitError` | Yes | Respects `Retry-After` header with exponential backoff & jitter. |
| **404 Model Not Found** | `LLMModelNotFoundError` | No | Indicates deprecated or unavailable free model ID. |
| **5xx Gateway / Server** | `LLMServiceUnavailableError` | Yes | Automatically retried up to `OPENROUTER_MAX_RETRIES`. |
| **Timeout / Network** | `LLMTimeoutError` / `LLMNetworkError` | Yes | Retried with backoff. |

### Reasoning Block (<think>...</think>) Suppression
Reasoning models (like DeepSeek R1 or Qwen) include `<think>...</think>` internal monologues in their output. `OpenRouterProvider` automatically parses and strips these tags before passing text to `AstraAgent` and `ElevenLabsTTS`, ensuring only natural, conversational responses are spoken aloud.

---

## 9. Verification & Test Suite

The OpenRouter provider has comprehensive unit, integration, and security test coverage in `tests/test_openrouter_provider.py`.

### Running OpenRouter Unit & Integration Tests:
```powershell
pytest tests/test_openrouter_provider.py -v
```

### Running Complete Project Regression Suite:
```powershell
pytest -q
```

---

## 10. Live Testing with a Real API Key

Live testing against OpenRouter's live API is opt-in and safe:

1. Set your OpenRouter API key in your current shell:
   ```powershell
   $env:OPENROUTER_API_KEY = "sk-or-v1-your-actual-api-key"
   $env:OPENROUTER_MODEL = "openrouter/free"
   ```
2. Run pytest targeting the integration test:
   ```powershell
   pytest tests/test_openrouter_provider.py -k test_real_openrouter_api_if_key_available -v -s
   ```
3. When the test completes, clear your shell environment:
   ```powershell
   $env:OPENROUTER_API_KEY = $null
   ```
