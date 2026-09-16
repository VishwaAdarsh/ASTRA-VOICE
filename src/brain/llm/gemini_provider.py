"""
Google Gemini Real LLM Provider Integration (Phase 14 & 15).
Communicates with Google Gemini API using the official google-genai SDK.
Supports structured tool schema conversion and Gemini function-calling representations.
"""

import os
import re
import time
from typing import Any
from google import genai
from google.genai import types
from google.genai.errors import APIError

from src.brain.llm.errors import (
    LLMAuthError,
    LLMConfigError,
    LLMContentPolicyError,
    LLMInvalidRequestError,
    LLMModelNotFoundError,
    LLMNetworkError,
    LLMProviderError,
    LLMQuotaExhaustedError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)
from src.brain.llm.models import DecisionType, LLMDecision, LLMUsage, ModelConfig
from src.brain.llm.provider import LLMProvider
from src.core.logger import get_logger

logger = get_logger()


class GeminiProvider(LLMProvider):
    """Real Google Gemini LLM Provider implementation with Function Calling support."""

    def __init__(self, config: ModelConfig | None = None):
        super().__init__(config=config)
        self.capabilities: set[str] = {"text", "structured", "tools"}

        # Authenticate using configuration or environment variables securely
        self.api_key = (
            self.config.api_key
            or os.getenv("LLM_API_KEY", "")
            or os.getenv("ASTRA_API_KEY", "")
            or os.getenv("GEMINI_API_KEY", "")
        ).strip()

        if not self.api_key:
            raise LLMConfigError(
                "Gemini API key is missing. Set LLM_API_KEY in .env or provide via ModelConfig.",
                provider="gemini",
            )

        # Determine target Gemini model name (defaulting to gemini-3.6-flash if generic mock default)
        model_setting = (self.config.model_name or self.config.model or "").strip().lower()
        if model_setting in ("mock-astra-v1", "default", "", "mock"):
            self.model_name = "gemini-3.6-flash"
        else:
            self.model_name = self.config.model_name or self.config.model

        try:
            self.client = genai.Client(api_key=self.api_key)
            self._cached_gemini_tools: list[types.Tool] | None = None
            self._cached_schema_len: int = 0
            logger.info(f"Initialized GeminiProvider (model='{self.model_name}')")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini Client: {e}")
            raise LLMConfigError(f"Failed to initialize Gemini API client: {e}", provider="gemini")

    @staticmethod
    def _parse_retry_after(message: str) -> float | None:
        """Extract retry-after duration in seconds from error text if present."""
        m = re.search(
            r"retry(?:\s+after|\s+in|after)?[:\s]+(\d+(?:\.\d+)?)\s*(?:s|sec|seconds)?",
            message,
            re.IGNORECASE,
        )
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass
        return None

    def _classify_api_error(self, ae: APIError) -> LLMProviderError:
        """Map raw Gemini APIError into typed LLMProviderError subclass."""
        code = getattr(ae, "code", None) or getattr(ae, "status_code", None)
        msg = str(ae)
        msg_lower = msg.lower()
        retry_after = self._parse_retry_after(msg)

        if code in (401, 403) or "unauthenticated" in msg_lower or "permission_denied" in msg_lower or "api key not valid" in msg_lower:
            return LLMAuthError(
                f"Gemini authentication failed: {msg}",
                provider="gemini",
                status_code=code or 401,
            )

        if code == 404 or "not_found" in msg_lower or "model not found" in msg_lower:
            return LLMModelNotFoundError(
                f"Gemini model '{self.model_name}' not found: {msg}",
                provider="gemini",
                status_code=404,
            )

        if code == 429 or "resource_exhausted" in msg_lower:
            # Distinguish permanent daily quota exhaustion from transient per-minute rate limiting
            is_daily_quota = (
                "generaterequestsperday" in msg_lower
                or "quota exceeded" in msg_lower
                or "quotaid" in msg_lower
                or "free_tier" in msg_lower
                or "daily" in msg_lower
                or "limit: 20" in msg_lower
                or ("resource_exhausted" in msg_lower and retry_after is None and "minute" not in msg_lower)
            )
            if is_daily_quota:
                return LLMQuotaExhaustedError(
                    f"Gemini daily quota exhausted: {msg}",
                    provider="gemini",
                    status_code=429,
                )
            return LLMRateLimitError(
                f"Gemini rate limit encountered: {msg}",
                provider="gemini",
                status_code=429,
                retry_after=retry_after or 2.0,
            )

        if code == 400 or "invalid_argument" in msg_lower:
            if "safety" in msg_lower or "blocked" in msg_lower or "harm" in msg_lower:
                return LLMContentPolicyError(
                    f"Gemini content policy violation: {msg}",
                    provider="gemini",
                    status_code=400,
                )
            return LLMInvalidRequestError(
                f"Gemini invalid request: {msg}",
                provider="gemini",
                status_code=400,
            )

        if code in (500, 502, 503, 504) or "unavailable" in msg_lower or "internal" in msg_lower:
            return LLMServiceUnavailableError(
                f"Gemini service unavailable: {msg}",
                provider="gemini",
                status_code=code or 503,
            )

        return LLMProviderError(f"Gemini API error: {msg}", provider="gemini", status_code=code)

    def _classify_generic_error(self, e: Exception) -> LLMProviderError:
        """Map generic network/runtime exceptions into typed LLMProviderError subclass."""
        msg = str(e)
        msg_lower = msg.lower()
        if isinstance(e, TimeoutError) or "timeout" in type(e).__name__.lower() or "timed out" in msg_lower:
            return LLMTimeoutError(f"Gemini request timed out: {msg}", provider="gemini")
        if isinstance(e, ConnectionError) or "connection" in msg_lower or "network" in msg_lower:
            return LLMNetworkError(f"Gemini network connection error: {msg}", provider="gemini")
        return LLMProviderError(f"Gemini request failed: {msg}", provider="gemini")

    def _convert_tool_schemas(
        self, tool_schemas: list[dict[str, Any]] | None
    ) -> list[types.Tool] | None:
        """Convert ASTRA tool schemas to Gemini API Tool FunctionDeclarations with caching."""
        if not tool_schemas:
            return None

        if self._cached_gemini_tools is not None and len(tool_schemas) == self._cached_schema_len:
            return self._cached_gemini_tools

        function_declarations: list[types.FunctionDeclaration] = []
        for schema in tool_schemas:
            try:
                name = schema.get("name", "")
                description = schema.get("description", "")
                if not name or not description:
                    continue

                parameters = schema.get(
                    "parameters",
                    {"type": "object", "properties": {}, "required": []},
                )

                func_decl = types.FunctionDeclaration(
                    name=name,
                    description=description,
                    parameters=parameters,
                )
                function_declarations.append(func_decl)
            except Exception as e:
                logger.warning(f"Failed to convert schema for tool '{schema.get('name')}': {e}")
                continue

        if not function_declarations:
            return None

        converted = [types.Tool(function_declarations=function_declarations)]
        self._cached_gemini_tools = converted
        self._cached_schema_len = len(tool_schemas)
        return converted

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate text completion from Google Gemini API."""
        start_time = time.time()
        logger.info(f"[LLM] Gemini text request started (model='{self.model_name}')")

        try:
            gen_config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=self.config.temperature,
                max_output_tokens=self.config.max_output_tokens,
            )

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=gen_config,
            )

            result_text = (response.text or "").strip()
            latency_ms = (time.time() - start_time) * 1000
            logger.info(f"[LLM] Gemini response received in {latency_ms:.1f}ms")
            return result_text

        except APIError as ae:
            err = self._classify_api_error(ae)
            logger.error(f"[LLM] Gemini API error ({type(err).__name__}): {err.message}")
            raise err from ae
        except LLMProviderError:
            raise
        except Exception as e:
            err = self._classify_generic_error(e)
            logger.error(f"[LLM] Gemini unexpected failure ({type(err).__name__}): {err.message}")
            raise err from e

    def generate_structured(
        self,
        prompt: str,
        system_prompt: str | None = None,
        tool_schemas: list[dict[str, Any]] | None = None,
    ) -> LLMDecision:
        """Generate decision from Gemini API with structured function calling support (Phase 15)."""
        start_time = time.time()
        logger.info(
            f"[LLM] Gemini structured request started (model='{self.model_name}', tools={len(tool_schemas or [])})"
        )

        try:
            gemini_tools = self._convert_tool_schemas(tool_schemas)
            gen_config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=self.config.temperature,
                max_output_tokens=self.config.max_output_tokens,
                tools=gemini_tools,
            )

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=gen_config,
            )

            latency_ms = (time.time() - start_time) * 1000
            prompt_tokens = max(1, len(prompt) // 4)
            usage = LLMUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=10,
                total_tokens=prompt_tokens + 10,
                latency_ms=latency_ms,
            )

            # Check for Gemini Function Call
            if response.function_calls:
                fc = response.function_calls[0]
                tool_name = fc.name
                arguments = dict(fc.args or {})
                logger.info(f"[LLM] Gemini selected tool: '{tool_name}' with args: {arguments}")

                return LLMDecision(
                    decision_type=DecisionType.TOOL_CALL,
                    tool_name=tool_name,
                    arguments=arguments,
                    raw_response=str(response.text or ""),
                    usage=usage,
                )

            # Normal conversational text response
            result_text = (response.text or "").strip()
            usage.completion_tokens = max(1, len(result_text) // 4)
            usage.total_tokens = prompt_tokens + usage.completion_tokens

            return LLMDecision(
                decision_type=DecisionType.RESPONSE,
                message=result_text,
                raw_response=result_text,
                usage=usage,
            )

        except APIError as ae:
            err = self._classify_api_error(ae)
            logger.error(f"[LLM] Gemini API error ({type(err).__name__}): {err.message}")
            raise err from ae
        except LLMProviderError:
            raise
        except Exception as e:
            err = self._classify_generic_error(e)
            logger.error(f"[LLM] Gemini unexpected failure ({type(err).__name__}): {err.message}")
            raise err from e

    def check_health(self) -> dict[str, Any]:
        """Verify Gemini provider initialization and configuration health."""
        if not self.api_key:
            return {
                "status": "unhealthy",
                "provider": "gemini",
                "model": self.model_name,
                "error": "API key missing",
                "capabilities": list(self.capabilities),
            }
        return {
            "status": "healthy",
            "provider": "gemini",
            "model": self.model_name,
            "authenticated": True,
            "capabilities": list(self.capabilities),
        }

    def shutdown(self) -> None:
        """Clean up provider resources."""
        self._cached_gemini_tools = None
        self._cached_schema_len = 0
        if hasattr(self.client, "close") and callable(self.client.close):
            try:
                self.client.close()
            except Exception as e:
                logger.warning(f"Error during Gemini client shutdown: {e}")

