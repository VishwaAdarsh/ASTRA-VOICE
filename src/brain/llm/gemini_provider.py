"""
Google Gemini Real LLM Provider Integration (Phase 14).
Communicates with Google Gemini API using the official google-genai SDK.
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
    """Real Google Gemini LLM Provider implementation."""

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

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate text completion from Google Gemini API."""
        start_time = time.time()
        logger.info(f"[LLM] Gemini request started (model='{self.model_name}')")

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
        """Generate conversational decision from Gemini API (Phase 14: Text Response Only)."""
        start_time = time.time()
        raw_text = self.generate(prompt=prompt, system_prompt=system_prompt)
        latency_ms = (time.time() - start_time) * 1000

        # Estimate usage token metrics safely
        prompt_tokens = max(1, len(prompt) // 4)
        completion_tokens = max(1, len(raw_text) // 4)
        usage = LLMUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
        )

        return LLMDecision(
            decision_type=DecisionType.RESPONSE,
            message=raw_text,
            raw_response=raw_text,
            usage=usage,
        )
