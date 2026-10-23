"""
OpenRouter Real LLM Provider Integration (Free Models Only by Default).

Talks to the OpenRouter Chat Completions API (``https://openrouter.ai/api/v1/chat/completions``) using
Bearer authentication, and adapts it to ASTRA's canonical ``LLMProvider`` interface:

    Agent -> LLMClient -> LLMProvider (canonical) -> OpenRouterProvider -> POST {base_url}{chat_endpoint}

Strict Cost & Security Rules:
- Default model: ``openrouter/free`` (official OpenRouter free model router).
- Cost Protection: Only verified free models (``openrouter/free`` or models ending with ``:free``)
  are permitted by default. If a paid model is requested without ``OPENROUTER_ALLOW_PAID_MODELS=true``,
  the provider fails closed at configuration time.
- Single HTTP attempt per call. Bounded retries with backoff/jitter are owned by ``LLMClient``.
- Every failure is mapped into ASTRA's typed ``LLMProviderError`` taxonomy.
- The API key is read from configuration/environment only and is NEVER logged, returned,
  placed in exceptions, or exposed through ``repr``.
- Internal reasoning blocks (<think>...</think>) are stripped; only final content reaches Agent / TTS.
- Structured tool calls are normalized into ASTRA's canonical ``{"name", "arguments"}`` structure.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from typing import Any
from urllib.parse import urlparse

import httpx

from src.brain.llm.errors import (
    LLMAuthError,
    LLMConfigError,
    LLMInvalidRequestError,
    LLMModelNotFoundError,
    LLMNetworkError,
    LLMProviderError,
    LLMQuotaExhaustedError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)
from src.brain.llm.models import DecisionType, LLMDecision, LLMMessage, LLMUsage, ModelConfig
from src.brain.llm.provider import LLMProvider
from src.core.logger import SecretRedactionFilter, get_logger

logger = get_logger()

PROVIDER_NAME = "openrouter"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_CHAT_ENDPOINT = "/chat/completions"
DEFAULT_MODEL = "openrouter/free"
_MAX_ERROR_DETAIL_CHARS = 300
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
_QUOTA_HINTS = (
    "quota",
    "usage limit",
    "credit",
    "billing",
    "subscription",
    "upgrade",
    "balance",
    "free tier",
    "daily",
)

# Known verified free models on OpenRouter
VERIFIED_FREE_MODELS = {
    "openrouter/free",
    "openrouter/free:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "google/gemma-3-27b-it:free",
    "google/gemini-2.0-flash-exp:free",
    "google/gemini-2.0-flash-thinking-exp:free",
    "mistralai/mistral-small-24b-instruct-2501:free",
    "deepseek/deepseek-r1:free",
    "deepseek/deepseek-chat:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "qwen/qwen-2.5-coder-32b-instruct:free",
    "sophosympatheia/rogue-rose-103b-v0.2:free",
}


class OpenRouterProvider(LLMProvider):
    """Real OpenRouter LLM provider with free-model cost protection and tool-calling support."""

    def __init__(self, config: ModelConfig | None = None, http_client: httpx.Client | None = None):
        super().__init__(config=config)
        self.capabilities = {"text", "structured", "tools", "chat"}

        # --- Credentials (environment / secure config only) --------------------------------
        self._api_key: str = (self.config.api_key or os.getenv("OPENROUTER_API_KEY", "")).strip()
        if not self._api_key:
            raise LLMConfigError(
                "OPENROUTER_API_KEY is not configured in the environment or configuration.",
                provider=PROVIDER_NAME,
            )

        # --- Model resolution & Free-only enforcement ---------------------------------------
        raw_model = (self.config.model_name or self.config.model or os.getenv("OPENROUTER_MODEL", "") or DEFAULT_MODEL).strip()
        self.model_name = raw_model or DEFAULT_MODEL

        self.allow_paid_models: bool = bool(
            getattr(self.config, "allow_paid_models", False)
            or os.getenv("OPENROUTER_ALLOW_PAID_MODELS", "false").lower() in ("true", "1", "yes")
        )

        # Enforce cost protection: only free models allowed unless explicitly configured
        if not self.allow_paid_models and not self.is_free_model(self.model_name):
            raise LLMConfigError(
                f"Model '{self.model_name}' is not an eligible free model on OpenRouter. "
                f"ASTRA cost protection requires 'openrouter/free' or a model ending with ':free' "
                f"unless OPENROUTER_ALLOW_PAID_MODELS=true is explicitly configured.",
                provider=PROVIDER_NAME,
            )

        # --- Endpoint -----------------------------------------------------------------------
        base_url = (self.config.base_url or os.getenv("OPENROUTER_BASE_URL", "") or DEFAULT_BASE_URL).strip().rstrip("/")
        endpoint = (self.config.chat_endpoint or os.getenv("OPENROUTER_CHAT_ENDPOINT", "") or DEFAULT_CHAT_ENDPOINT).strip()
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        parsed = urlparse(base_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise LLMConfigError(
                f"Invalid OPENROUTER_BASE_URL '{base_url}'. Expected an absolute http(s) URL such as {DEFAULT_BASE_URL}.",
                provider=PROVIDER_NAME,
            )
        self.base_url = base_url
        self.chat_endpoint = endpoint
        self.chat_url = f"{base_url}{endpoint}"

        # --- Optional App Attribution Headers ----------------------------------------------
        self.site_url: str = getattr(self.config, "site_url", "") or os.getenv("OPENROUTER_SITE_URL", "").strip()
        self.app_name: str = getattr(self.config, "app_name", "") or os.getenv("OPENROUTER_APP_NAME", "ASTRA").strip()

        # --- Timeouts & Client --------------------------------------------------------------
        self.timeout = float(self.config.timeout or os.getenv("OPENROUTER_TIMEOUT", "45"))
        self._external_client = http_client is not None
        self._client = http_client or httpx.Client(timeout=self.timeout)

    @classmethod
    def is_free_model(cls, model_id: str) -> bool:
        """Verify whether a model ID is guaranteed to be a free tier model on OpenRouter."""
        clean = (model_id or "").strip().lower()
        if clean in ("openrouter/free", "openrouter/free:free"):
            return True
        if clean.endswith(":free"):
            return True
        if clean in VERIFIED_FREE_MODELS:
            return True
        return False

    def __repr__(self) -> str:
        # Never expose API key in repr
        return f"OpenRouterProvider(model='{self.model_name}', base_url='{self.base_url}', allow_paid={self.allow_paid_models})"

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.app_name:
            headers["X-Title"] = self.app_name
        return headers

    def _scrub(self, s: Any) -> str:
        """Sanitize text to guarantee the API key is never exposed in logs or errors."""
        s = "" if s is None else str(s)
        if self._api_key:
            s = s.replace(self._api_key, "[REDACTED]")
        return SecretRedactionFilter.redact(s)

    # ------------------------------------------------------------------------------------------
    # Canonical -> OpenRouter conversion
    # ------------------------------------------------------------------------------------------
    @staticmethod
    def convert_messages(messages: list[LLMMessage | dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert canonical messages into OpenAI/OpenRouter chat messages."""
        converted: list[dict[str, Any]] = []
        for i, m in enumerate(messages):
            if isinstance(m, LLMMessage):
                role, content, tool_calls, name = m.role, m.content, m.tool_calls, m.name
            else:
                role = m.get("role", "user")
                content = m.get("content", "")
                tool_calls = m.get("tool_calls") or []
                name = m.get("name") or m.get("tool_name")
            role = str(role).strip().lower()
            if role not in ("system", "user", "assistant", "tool"):
                raise LLMInvalidRequestError(f"Unsupported message role '{role}'.", provider=PROVIDER_NAME)

            msg: dict[str, Any] = {"role": role, "content": "" if content is None else str(content)}

            if role == "assistant" and tool_calls:
                msg["tool_calls"] = [
                    {
                        "id": tc.get("id") or f"call_{i}_{uuid.uuid4().hex[:6]}",
                        "type": "function",
                        "function": {
                            "name": tc.get("name"),
                            "arguments": json.dumps(tc.get("arguments", {}))
                            if isinstance(tc.get("arguments"), dict)
                            else str(tc.get("arguments", "{}")),
                        },
                    }
                    for tc in tool_calls
                ]

            if role == "tool":
                call_id = getattr(m, "tool_call_id", None) if isinstance(m, LLMMessage) else m.get("tool_call_id")
                msg["tool_call_id"] = call_id or f"call_{i}"
                if name:
                    msg["name"] = name

            converted.append(msg)
        return converted

    @staticmethod
    def convert_tool_schemas(tool_schemas: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        """Convert ASTRA canonical tool schemas ({name, description, parameters}) to OpenRouter/OpenAI tools."""
        tools: list[dict[str, Any]] = []
        for schema in tool_schemas or []:
            name = (schema or {}).get("name")
            if not name:
                continue
            params = schema.get("parameters") or {"type": "object", "properties": {}, "required": []}
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": schema.get("description", ""),
                        "parameters": params,
                    },
                }
            )
        return tools

    def build_payload(
        self,
        messages: list[LLMMessage | dict[str, Any]],
        tool_schemas: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": self.convert_messages(messages),
            "stream": False,
        }
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature
        if self.config.max_output_tokens:
            payload["max_tokens"] = int(self.config.max_output_tokens)

        tools = self.convert_tool_schemas(tool_schemas)
        if tools:
            payload["tools"] = tools

        return payload

    @staticmethod
    def _base_messages(prompt: str, system_prompt: str | None) -> list[LLMMessage]:
        msgs: list[LLMMessage] = []
        if system_prompt:
            msgs.append(LLMMessage(role="system", content=system_prompt))
        msgs.append(LLMMessage(role="user", content=prompt))
        return msgs

    # ------------------------------------------------------------------------------------------
    # HTTP transport + error taxonomy
    # ------------------------------------------------------------------------------------------
    def _extract_error_detail(self, response: httpx.Response) -> str:
        detail = ""
        try:
            body = response.json()
            if isinstance(body, dict):
                err = body.get("error")
                if isinstance(err, dict):
                    detail = str(err.get("message") or err)
                elif err:
                    detail = str(err)
        except Exception:
            detail = response.text or ""
        detail = self._scrub(detail).strip()
        return detail[:_MAX_ERROR_DETAIL_CHARS] or f"HTTP {response.status_code}"

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        raw = response.headers.get("retry-after")
        if not raw:
            return None
        try:
            return max(0.0, float(raw))
        except ValueError:
            return None

    def classify_http_error(self, response: httpx.Response) -> LLMProviderError:
        """Map an OpenRouter HTTP error response into ASTRA's typed error taxonomy."""
        code = response.status_code
        detail = self._extract_error_detail(response)
        low = detail.lower()
        details = {"status_code": code}

        if code in (401, 403):
            return LLMAuthError(
                f"OpenRouter authentication failed: {detail}",
                provider=PROVIDER_NAME,
                status_code=code,
                details=details,
            )
        if code == 402 or (code == 429 and any(h in low for h in _QUOTA_HINTS)):
            return LLMQuotaExhaustedError(
                f"OpenRouter usage quota exhausted: {detail}",
                provider=PROVIDER_NAME,
                status_code=code,
                retry_after=self._retry_after(response),
                details=details,
            )
        if code == 429:
            return LLMRateLimitError(
                f"OpenRouter rate limit encountered: {detail}",
                provider=PROVIDER_NAME,
                retry_after=self._retry_after(response) or 2.0,
                status_code=429,
                details=details,
            )
        if code == 404 or ("model" in low and "not found" in low):
            return LLMModelNotFoundError(
                f"OpenRouter model '{self.model_name}' not found: {detail}",
                provider=PROVIDER_NAME,
                status_code=code,
                details=details,
            )
        if code == 408:
            return LLMTimeoutError(
                f"OpenRouter request timed out (HTTP 408): {detail}",
                provider=PROVIDER_NAME,
                details=details,
            )
        if code in (400, 413, 422):
            return LLMInvalidRequestError(
                f"OpenRouter rejected the request: {detail}",
                provider=PROVIDER_NAME,
                status_code=code,
                details=details,
            )
        if code >= 500:
            return LLMServiceUnavailableError(
                f"OpenRouter service unavailable: {detail}",
                provider=PROVIDER_NAME,
                status_code=code,
                details=details,
            )
        return LLMProviderError(
            f"OpenRouter API error: {detail}",
            provider=PROVIDER_NAME,
            status_code=code,
            retryable=False,
            details=details,
        )

    def _post_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send exactly one chat request. Never logs headers, credentials, or prompt content."""
        request_id = uuid.uuid4().hex[:12]
        start = time.perf_counter()
        logger.info(
            f"[LLM] OpenRouter request started (request_id={request_id}, model='{self.model_name}', "
            f"messages={len(payload.get('messages', []))}, tools={len(payload.get('tools', []))})"
        )
        try:
            response = self._client.post(self.chat_url, json=payload, headers=self._headers(), timeout=self.timeout)
        except httpx.TimeoutException as e:
            duration = (time.perf_counter() - start) * 1000
            logger.error(f"[LLM] OpenRouter request failed (request_id={request_id}, category=TIMEOUT, duration={duration:.0f}ms)")
            raise LLMTimeoutError(f"OpenRouter request timed out after {self.timeout:.0f}s.", provider=PROVIDER_NAME) from e
        except httpx.TransportError as e:
            duration = (time.perf_counter() - start) * 1000
            logger.error(
                f"[LLM] OpenRouter request failed (request_id={request_id}, category=NETWORK_ERROR, "
                f"duration={duration:.0f}ms, error={type(e).__name__})"
            )
            raise LLMNetworkError(
                f"Unable to reach OpenRouter at {self.base_url}: {self._scrub(type(e).__name__)}", provider=PROVIDER_NAME
            ) from e

        duration = (time.perf_counter() - start) * 1000
        if response.status_code != 200:
            err = self.classify_http_error(response)
            logger.error(
                f"[LLM] OpenRouter request failed (request_id={request_id}, status={response.status_code}, "
                f"category={err.error_type.value}, duration={duration:.0f}ms)"
            )
            raise err

        try:
            data = response.json()
        except (ValueError, json.JSONDecodeError) as e:
            logger.error(f"[LLM] OpenRouter returned non-JSON body (request_id={request_id}, duration={duration:.0f}ms)")
            raise LLMProviderError(
                "OpenRouter returned a malformed (non-JSON) response.",
                provider=PROVIDER_NAME,
                status_code=200,
            ) from e

        if not isinstance(data, dict):
            raise LLMProviderError("OpenRouter returned an unexpected response shape.", provider=PROVIDER_NAME, status_code=200)
        if data.get("error"):
            raise LLMProviderError(
                f"OpenRouter reported an error: {self._scrub(data.get('error'))[:_MAX_ERROR_DETAIL_CHARS]}",
                provider=PROVIDER_NAME,
                status_code=200,
            )

        logger.info(
            f"[LLM] OpenRouter response received (request_id={request_id}, status=200, duration={duration:.0f}ms, "
            f"size={len(response.content)}B)"
        )
        data["_astra_latency_ms"] = duration
        return data

    # ------------------------------------------------------------------------------------------
    # OpenRouter -> canonical normalization
    # ------------------------------------------------------------------------------------------
    @staticmethod
    def _clean_content(content: Any) -> str:
        """Final user-facing text only: strips any inline reasoning blocks."""
        text = "" if content is None else str(content)
        return _THINK_BLOCK_RE.sub("", text).strip()

    def normalize_tool_calls(self, raw_calls: Any) -> list[dict[str, Any]]:
        """Normalize OpenRouter/OpenAI tool_calls into ASTRA canonical [{"name": str, "arguments": dict}]."""
        normalized: list[dict[str, Any]] = []
        if not raw_calls:
            return normalized
        if not isinstance(raw_calls, list):
            raise LLMProviderError("OpenRouter returned malformed tool_calls (expected a list).", provider=PROVIDER_NAME)
        for call in raw_calls:
            fn = (call or {}).get("function") if isinstance(call, dict) else None
            if not isinstance(fn, dict) or not fn.get("name"):
                raise LLMProviderError("OpenRouter returned a tool call without a function name.", provider=PROVIDER_NAME)
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args) if args.strip() else {}
                except json.JSONDecodeError as e:
                    raise LLMProviderError(
                        f"OpenRouter returned non-JSON arguments for tool '{fn['name']}'.", provider=PROVIDER_NAME
                    ) from e
            if args is None:
                args = {}
            if not isinstance(args, dict):
                raise LLMProviderError(
                    f"OpenRouter returned invalid arguments for tool '{fn['name']}' (expected an object).",
                    provider=PROVIDER_NAME,
                )
            call_id = call.get("id") or f"call_{uuid.uuid4().hex[:8]}"
            normalized.append({"id": call_id, "name": str(fn["name"]).strip(), "arguments": args})
        return normalized

    def normalize_response(self, data: dict[str, Any], tool_schemas: list[dict[str, Any]] | None = None) -> LLMDecision:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMProviderError("OpenRouter response is missing the 'choices' array.", provider=PROVIDER_NAME, status_code=200)

        choice = choices[0] or {}
        message = choice.get("message")
        if not isinstance(message, dict):
            raise LLMProviderError("OpenRouter choice is missing the 'message' object.", provider=PROVIDER_NAME, status_code=200)

        content = self._clean_content(message.get("content"))
        tool_calls = self.normalize_tool_calls(message.get("tool_calls"))

        usage_data = data.get("usage") or {}
        prompt_tokens = int(usage_data.get("prompt_tokens") or 0)
        completion_tokens = int(usage_data.get("completion_tokens") or 0)
        total_tokens = int(usage_data.get("total_tokens") or (prompt_tokens + completion_tokens))

        usage = LLMUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=float(data.get("_astra_latency_ms") or 0.0),
        )

        if tool_calls:
            first = tool_calls[0]
            known = {s.get("name") for s in (tool_schemas or [])}
            if known and first["name"] not in known:
                logger.warning(f"[LLM] OpenRouter selected unknown tool '{first['name']}'; ToolRegistry/ToolExecutor will reject it.")
            logger.info(f"[LLM] OpenRouter selected tool '{first['name']}' ({len(tool_calls)} call(s) returned)")
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name=first["name"],
                arguments=first["arguments"],
                message=content or None,
                raw_response=content,
                usage=usage,
                provider=PROVIDER_NAME,
                model=self.model_name,
                tool_calls=tool_calls,
            )

        if not content:
            raise LLMProviderError(
                f"OpenRouter returned an empty response (finish_reason={choice.get('finish_reason')}).",
                provider=PROVIDER_NAME,
                status_code=200,
            )

        return LLMDecision(
            decision_type=DecisionType.RESPONSE,
            message=content,
            raw_response=content,
            usage=usage,
            provider=PROVIDER_NAME,
            model=self.model_name,
        )

    # ------------------------------------------------------------------------------------------
    # LLMProvider interface implementations
    # ------------------------------------------------------------------------------------------
    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate raw text response via OpenRouter."""
        messages = self._base_messages(prompt, system_prompt)
        payload = self.build_payload(messages=messages, tool_schemas=None)
        data = self._post_chat(payload)
        decision = self.normalize_response(data, tool_schemas=None)
        return decision.message or ""

    def generate_structured(
        self,
        prompt: str,
        system_prompt: str | None = None,
        tool_schemas: list[dict[str, Any]] | None = None,
    ) -> LLMDecision:
        """Generate structured decision or tool call via OpenRouter."""
        messages = self._base_messages(prompt, system_prompt)
        payload = self.build_payload(messages=messages, tool_schemas=tool_schemas)
        data = self._post_chat(payload)
        return self.normalize_response(data, tool_schemas=tool_schemas)

    def check_health(self) -> dict[str, Any]:
        """Check provider health and configured free-model status."""
        return {
            "status": "ok",
            "provider": PROVIDER_NAME,
            "model": self.model_name,
            "is_free": self.is_free_model(self.model_name),
            "endpoint": self.chat_url,
        }

    def shutdown(self) -> None:
        """Clean up HTTP client connections."""
        if not self._external_client:
            try:
                self._client.close()
            except Exception as e:
                logger.debug(f"OpenRouterProvider client close notice: {e}")
