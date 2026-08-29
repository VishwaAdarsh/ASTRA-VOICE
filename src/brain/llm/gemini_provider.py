"""
Google Gemini Real LLM Provider Integration (Phase 14 & 15).
Communicates with Google Gemini API using the official google-genai SDK.
Supports structured tool schema conversion and Gemini function-calling representations.
"""

import os
import time
from typing import Any
from google import genai
from google.genai import types
from google.genai.errors import APIError

from src.brain.llm.models import DecisionType, LLMDecision, LLMUsage, ModelConfig
from src.brain.llm.provider import LLMProvider
from src.core.exceptions import LLMProviderError
from src.core.logger import get_logger

logger = get_logger()


class GeminiProvider(LLMProvider):
    """Real Google Gemini LLM Provider implementation with Function Calling support."""

    def __init__(self, config: ModelConfig | None = None):
        super().__init__(config=config)

        # Authenticate using configuration or environment variables securely
        self.api_key = (
            self.config.api_key
            or os.getenv("LLM_API_KEY", "")
            or os.getenv("ASTRA_API_KEY", "")
        ).strip()

        if not self.api_key:
            raise LLMProviderError(
                "Gemini API key is missing. Set LLM_API_KEY in .env or provide via ModelConfig."
            )

        # Determine target Gemini model name (defaulting to gemini-3.6-flash if generic mock default)
        model_setting = self.config.model.strip().lower()
        if model_setting in ("mock-astra-v1", "default", "", "mock"):
            self.model_name = "gemini-3.6-flash"
        else:
            self.model_name = self.config.model

        try:
            self.client = genai.Client(api_key=self.api_key)
            logger.info(f"Initialized GeminiProvider (model='{self.model_name}')")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini Client: {e}")
            raise LLMProviderError(f"Failed to initialize Gemini API client: {e}")

    def _convert_tool_schemas(
        self, tool_schemas: list[dict[str, Any]] | None
    ) -> list[types.Tool] | None:
        """Convert ASTRA tool schemas to Gemini API Tool FunctionDeclarations."""
        if not tool_schemas:
            return None

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

        return [types.Tool(function_declarations=function_declarations)]

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
            logger.error(f"[LLM] Gemini API error: {ae}")
            raise LLMProviderError(f"Gemini API call failed: {ae}")
        except Exception as e:
            logger.error(f"[LLM] Gemini unexpected failure: {e}")
            raise LLMProviderError(f"Gemini request failed: {e}")

    def generate_structured(
        self,
        prompt: str,
        system_prompt: str | None = None,
        tool_schemas: list[dict[str, Any]] | None = None,
    ) -> LLMDecision:
        """Generate decision from Gemini API with structured function calling support (Phase 15)."""
        start_time = time.time()
        logger.info(f"[LLM] Gemini structured request started (model='{self.model_name}', tools={len(tool_schemas or [])})")

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
            logger.error(f"[LLM] Gemini API error: {ae}")
            raise LLMProviderError(f"Gemini API call failed: {ae}")
        except Exception as e:
            logger.error(f"[LLM] Gemini structured request failed: {e}")
            raise LLMProviderError(f"Gemini request failed: {e}")
