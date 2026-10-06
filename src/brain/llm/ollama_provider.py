"""
Ollama Real LLM Provider Integration.

Talks to the Ollama chat API (default: Ollama Cloud, ``https://ollama.com/api/chat``) using
Bearer authentication, and adapts it to ASTRA's canonical ``LLMProvider`` interface:

    Agent -> LLMClient -> LLMProvider (canonical) -> OllamaProvider -> POST {base_url}{chat_endpoint}

Design rules:
- Implements the existing canonical interface only (``generate`` / ``generate_structured``)
  plus a canonical multi-turn ``chat`` helper; no Ollama-specific interface leaks to the Agent.
- Single HTTP attempt per call. Bounded retries with backoff/jitter are owned by ``LLMClient``.
- Every failure is mapped into ASTRA's typed ``LLMProviderError`` taxonomy.
- The API key is read from configuration/environment only and is NEVER logged, returned,
  placed in exceptions, or exposed through ``repr``.
- Internal reasoning ("thinking") returned by the model is discarded; only final content
  reaches the Agent / UI / TTS / memory.
- Tool calls are normalized into ASTRA's canonical ``{"name", "arguments"}`` structure. The
  model never executes anything; execution remains with ToolExecutor + PermissionManager.
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

PROVIDER_NAME = "ollama"
DEFAULT_BASE_URL = "https://ollama.com"
DEFAULT_CHAT_ENDPOINT = "/api/chat"
DEFAULT_MODEL = "gemma4:31b"
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
_PLACEHOLDER_MODELS = {"", "default", "mock", "mock-astra-v1"}
_MAX_ERROR_DETAIL_CHARS = 300
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
_QUOTA_HINTS = (
    "quota",
    "usage limit",
    "limit reached",
    "exceeded your",
    "billing",
    "subscription",
    "upgrade",
    "weekly",
    "daily",
    "monthly",
    "credits",
)


class OllamaProvider(LLMProvider):
    """Real Ollama LLM provider (Ollama Cloud by default) with function-calling support."""

    def __init__(self, config: ModelConfig | None = None, http_client: httpx.Client | None = None):
        super().__init__(config=config)
        self.capabilities = {"text", "structured", "tools", "chat"}

        # --- Credentials (environment / secure config only) --------------------------------
        self._api_key: str = (self.config.api_key or os.getenv("OLLAMA_API_KEY", "")).strip()

        # --- Endpoint -----------------------------------------------------------------------
        base_url = (self.config.base_url or os.getenv("OLLAMA_BASE_URL", "") or DEFAULT_BASE_URL).strip().rstrip("/")
        endpoint = (self.config.chat_endpoint or os.getenv("OLLAMA_CHAT_ENDPOINT", "") or DEFAULT_CHAT_ENDPOINT).strip()
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        parsed = urlparse(base_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise LLMConfigError(
                f"Invalid OLLAMA_BASE_URL '{base_url}'. Expected an absolute http(s) URL such as {DEFAULT_BASE_URL}.",
                provider=PROVIDER_NAME,
            )
        self.base_url = base_url
        self.chat_endpoint = endpoint
        self.chat_url = f"{base_url}{endpoint}"
        self.is_local = (parsed.hostname or "").lower() in _LOOPBACK_HOSTS

        # Cloud API requires a key. (A loopback base URL is only used if explicitly configured.)
        if not self._api_key and not self.is_local:
            raise LLMConfigError(
                "Ollama API key is missing. Set the OLLAMA_API_KEY environment variable "
                "(e.g. in your local, git-ignored .env file) when LLM_PROVIDER=ollama.",
                provider=PROVIDER_NAME,
            )

        # --- Model & generation options -------------------------------------------------------
        model_setting = (self.config.model_name or self.config.model or "").strip()
        self.model_name = DEFAULT_MODEL if model_setting.lower() in _PLACEHOLDER_MODELS else model_setting

        self.timeout = float(self.config.timeout or 60.0)
        if self.timeout <= 0:
            raise LLMConfigError("OLLAMA_TIMEOUT must be a positive number of seconds.", provider=PROVIDER_NAME)
        self.think = self._parse_think(self.config.think)

        # --- HTTP client (connection reuse) --------------------------------------------------
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(
            timeout=httpx.Timeout(self.timeout, connect=min(10.0, self.timeout)),
            follow_redirects=False,
        )

        logger.info(
            f"Initialized OllamaProvider (model='{self.model_name}', endpoint='{self.chat_url}', "
            f"timeout={self.timeout:.0f}s, auth={'configured' if self._api_key else 'none'})"
        )

    # ------------------------------------------------------------------------------------------
    # Representation / secrets
    # ------------------------------------------------------------------------------------------
    def __repr__(self) -> str:  # never include the key
        return f"OllamaProvider(model={self.model_name!r}, endpoint={self.chat_url!r})"

    @property
    def has_api_key(self) -> bool:
        return bool(self._api_key)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _scrub(self, text: Any) -> str:
        """Remove any credential material from text destined for logs or exceptions."""
        s = str(text or "")
        if self._api_key:
            s = s.replace(self._api_key, "[REDACTED]")
        return SecretRedactionFilter.redact(s)

    @staticmethod
    def _parse_think(value: Any) -> bool | str | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        v = str(value).strip().lower()
        if v in ("", "default", "none", "null"):
            return None
        if v in ("false", "0", "no", "off"):
            return False
        if v in ("true", "1", "yes", "on"):
            return True
        return v  # model-defined level, e.g. "low" | "medium" | "high"

    # ------------------------------------------------------------------------------------------
    # Canonical -> Ollama conversion
    # ------------------------------------------------------------------------------------------
    @staticmethod
    def convert_messages(messages: list[LLMMessage | dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert canonical messages into Ollama chat messages (order preserved, no concatenation)."""
        converted: list[dict[str, Any]] = []
        for m in messages:
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
                    {"function": {"name": tc.get("name"), "arguments": tc.get("arguments") or {}}}
                    for tc in tool_calls
                ]
            if role == "tool" and name:
                msg["tool_name"] = name
            converted.append(msg)
        return converted

    @staticmethod
    def convert_tool_schemas(tool_schemas: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        """Convert ASTRA canonical tool schemas ({name, description, parameters}) to Ollama tools."""
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
        options: dict[str, Any] = {}
        if self.config.temperature is not None:
            options["temperature"] = self.config.temperature
        if self.config.max_output_tokens:
            options["num_predict"] = int(self.config.max_output_tokens)
        if options:
            payload["options"] = options
        tools = self.convert_tool_schemas(tool_schemas)
        if tools:
            payload["tools"] = tools
        if self.think is not None:
            payload["think"] = self.think
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
        """Map an Ollama HTTP error response into ASTRA's typed error taxonomy."""
        code = response.status_code
        detail = self._extract_error_detail(response)
        low = detail.lower()
        details = {"status_code": code}

        if code in (401, 403):
            return LLMAuthError(f"Ollama authentication failed: {detail}", provider=PROVIDER_NAME, status_code=code, details=details)
        if code == 402 or (code == 429 and any(h in low for h in _QUOTA_HINTS)):
            return LLMQuotaExhaustedError(
                f"Ollama usage quota exhausted: {detail}",
                provider=PROVIDER_NAME,
                status_code=code,
                retry_after=self._retry_after(response),
                details=details,
            )
        if code == 429:
            return LLMRateLimitError(
                f"Ollama rate limit encountered: {detail}",
                provider=PROVIDER_NAME,
                retry_after=self._retry_after(response) or 2.0,
                status_code=429,
                details=details,
            )
        if code == 404 or ("model" in low and "not found" in low):
            return LLMModelNotFoundError(
                f"Ollama model '{self.model_name}' or endpoint not found: {detail}",
                provider=PROVIDER_NAME,
                status_code=code,
                details=details,
            )
        if code == 408:
            return LLMTimeoutError(f"Ollama request timed out (HTTP 408): {detail}", provider=PROVIDER_NAME, details=details)
        if code in (400, 413, 422):
            return LLMInvalidRequestError(f"Ollama rejected the request: {detail}", provider=PROVIDER_NAME, status_code=code, details=details)
        if code >= 500:
            return LLMServiceUnavailableError(f"Ollama service unavailable: {detail}", provider=PROVIDER_NAME, status_code=code, details=details)
        return LLMProviderError(f"Ollama API error: {detail}", provider=PROVIDER_NAME, status_code=code, retryable=False, details=details)

    def _post_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send exactly one chat request. Never logs headers, credentials, or prompt content."""
        request_id = uuid.uuid4().hex[:12]
        start = time.perf_counter()
        logger.info(
            f"[LLM] Ollama request started (request_id={request_id}, model='{self.model_name}', "
            f"messages={len(payload.get('messages', []))}, tools={len(payload.get('tools', []))})"
        )
        try:
            response = self._client.post(self.chat_url, json=payload, headers=self._headers(), timeout=self.timeout)
        except httpx.TimeoutException as e:
            duration = (time.perf_counter() - start) * 1000
            logger.error(f"[LLM] Ollama request failed (request_id={request_id}, category=TIMEOUT, duration={duration:.0f}ms)")
            raise LLMTimeoutError(f"Ollama request timed out after {self.timeout:.0f}s.", provider=PROVIDER_NAME) from e
        except httpx.TransportError as e:
            duration = (time.perf_counter() - start) * 1000
            logger.error(
                f"[LLM] Ollama request failed (request_id={request_id}, category=NETWORK_ERROR, "
                f"duration={duration:.0f}ms, error={type(e).__name__})"
            )
            raise LLMNetworkError(
                f"Unable to reach Ollama at {self.base_url}: {self._scrub(type(e).__name__)}", provider=PROVIDER_NAME
            ) from e

        duration = (time.perf_counter() - start) * 1000
        if response.status_code != 200:
            err = self.classify_http_error(response)
            logger.error(
                f"[LLM] Ollama request failed (request_id={request_id}, status={response.status_code}, "
                f"category={err.error_type.value}, duration={duration:.0f}ms)"
            )
            raise err

        try:
            data = response.json()
        except (ValueError, json.JSONDecodeError) as e:
            logger.error(f"[LLM] Ollama returned non-JSON body (request_id={request_id}, duration={duration:.0f}ms)")
            raise LLMProviderError("Ollama returned a malformed (non-JSON) response.", provider=PROVIDER_NAME, status_code=200) from e

        if not isinstance(data, dict):
            raise LLMProviderError("Ollama returned an unexpected response shape.", provider=PROVIDER_NAME, status_code=200)
        if data.get("error"):
            raise LLMProviderError(f"Ollama reported an error: {self._scrub(data.get('error'))[:_MAX_ERROR_DETAIL_CHARS]}", provider=PROVIDER_NAME, status_code=200)

        logger.info(
            f"[LLM] Ollama response received (request_id={request_id}, status=200, duration={duration:.0f}ms, "
            f"size={len(response.content)}B, done_reason={data.get('done_reason')})"
        )
        data["_astra_latency_ms"] = duration
        return data

    # ------------------------------------------------------------------------------------------
    # Ollama -> canonical normalization
    # ------------------------------------------------------------------------------------------
    @staticmethod
    def _clean_content(content: Any) -> str:
        """Final user-facing text only: strips any inline reasoning blocks."""
        text = "" if content is None else str(content)
        return _THINK_BLOCK_RE.sub("", text).strip()

    def normalize_tool_calls(self, raw_calls: Any) -> list[dict[str, Any]]:
        """Normalize Ollama tool_calls into ASTRA canonical [{"name": str, "arguments": dict}]."""
        normalized: list[dict[str, Any]] = []
        if not raw_calls:
            return normalized
        if not isinstance(raw_calls, list):
            raise LLMProviderError("Ollama returned malformed tool_calls (expected a list).", provider=PROVIDER_NAME)
        for call in raw_calls:
            fn = (call or {}).get("function") if isinstance(call, dict) else None
            if not isinstance(fn, dict) or not fn.get("name"):
                raise LLMProviderError("Ollama returned a tool call without a function name.", provider=PROVIDER_NAME)
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args) if args.strip() else {}
                except json.JSONDecodeError as e:
                    raise LLMProviderError(
                        f"Ollama returned non-JSON arguments for tool '{fn['name']}'.", provider=PROVIDER_NAME
                    ) from e
            if args is None:
                args = {}
            if not isinstance(args, dict):
                raise LLMProviderError(
                    f"Ollama returned invalid arguments for tool '{fn['name']}' (expected an object).",
                    provider=PROVIDER_NAME,
                )
            normalized.append({"name": str(fn["name"]).strip(), "arguments": args})
        return normalized

    def normalize_response(self, data: dict[str, Any], tool_schemas: list[dict[str, Any]] | None = None) -> LLMDecision:
        message = data.get("message")
        if not isinstance(message, dict):
            raise LLMProviderError("Ollama response is missing the 'message' object.", provider=PROVIDER_NAME, status_code=200)

        # NOTE: message.get("thinking") is intentionally ignored (never shown, spoken, or stored).
        content = self._clean_content(message.get("content"))
        tool_calls = self.normalize_tool_calls(message.get("tool_calls"))

        prompt_tokens = int(data.get("prompt_eval_count") or 0)
        completion_tokens = int(data.get("eval_count") or 0)
        usage = LLMUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=float(data.get("_astra_latency_ms") or 0.0),
        )

        if tool_calls:
            first = tool_calls[0]
            known = {s.get("name") for s in (tool_schemas or [])}
            if known and first["name"] not in known:
                logger.warning(f"[LLM] Ollama selected unknown tool '{first['name']}'; ToolRegistry/ToolExecutor will reject it.")
            logger.info(f"[LLM] Ollama selected tool '{first['name']}' ({len(tool_calls)} call(s) returned)")
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
                f"Ollama returned an empty response (done_reason={data.get('done_reason')}).",
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
    # Canonical LLMProvider interface
    # ------------------------------------------------------------------------------------------
    def chat(
        self,
        messages: list[LLMMessage | dict[str, Any]],
        tool_schemas: list[dict[str, Any]] | None = None,
    ) -> LLMDecision:
        """Canonical multi-turn chat (system/user/assistant/tool messages preserved as-is)."""
        payload = self.build_payload(messages, tool_schemas)
        data = self._post_chat(payload)
        return self.normalize_response(data, tool_schemas)

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        decision = self.chat(self._base_messages(prompt, system_prompt))
        return decision.message or ""

    def generate_structured(
        self,
        prompt: str,
        system_prompt: str | None = None,
        tool_schemas: list[dict[str, Any]] | None = None,
    ) -> LLMDecision:
        return self.chat(self._base_messages(prompt, system_prompt), tool_schemas)

    def check_health(self) -> dict[str, Any]:
        """Configuration-level health (no network call; real outcomes are tracked by LLMClient)."""
        configured = self.has_api_key or self.is_local
        return {
            "status": "healthy" if configured else "unhealthy",
            "provider": PROVIDER_NAME,
            "model": self.model_name,
            "endpoint": self.chat_url,
            "authenticated": self.has_api_key,
            "capabilities": sorted(self.capabilities),
            **({} if configured else {"error": "API key missing"}),
        }

    def shutdown(self) -> None:
        if self._owns_client:
            try:
                self._client.close()
            except Exception as e:
                logger.warning(f"Error during Ollama HTTP client shutdown: {type(e).__name__}")
