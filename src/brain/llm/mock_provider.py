"""
Mock LLM Provider for deterministic offline testing.
"""

import time
from typing import Any
from src.brain.llm.models import DecisionType, LLMDecision, LLMUsage, ModelConfig
from src.brain.llm.provider import LLMProvider


class MockLLMProvider(LLMProvider):
    """Mock LLM Provider for testing without external API calls or network dependency."""

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        return f"Mock LLM completion for: '{prompt}'"

    def generate_structured(
        self,
        prompt: str,
        system_prompt: str | None = None,
        tool_schemas: list[dict[str, Any]] | None = None,
    ) -> LLMDecision:
        start_time = time.time()
        text = prompt.lower().strip()

        usage = LLMUsage(
            prompt_tokens=len(prompt.split()),
            completion_tokens=15,
            total_tokens=len(prompt.split()) + 15,
            latency_ms=(time.time() - start_time) * 1000,
        )

        # 1. Match Open Application Intent
        if "calculator" in text or "calc" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="open_application",
                arguments={"app_name": "calculator"},
                reason="User requested opening calculator application.",
                usage=usage,
            )
        elif "notepad" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="open_application",
                arguments={"app_name": "notepad"},
                reason="User requested opening notepad application.",
                usage=usage,
            )
        elif "chrome" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="open_application",
                arguments={"app_name": "chrome"},
                reason="User requested opening chrome application.",
                usage=usage,
            )

        # 2. Match Open Folder Intent
        elif "downloads" in text or "download" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="open_folder",
                arguments={"folder_name": "downloads"},
                reason="User requested opening downloads folder.",
                usage=usage,
            )
        elif "documents" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="open_folder",
                arguments={"folder_name": "documents"},
                reason="User requested opening documents folder.",
                usage=usage,
            )

        # 3. Match Open Website Intent
        elif "youtube" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="open_website",
                arguments={"target": "youtube"},
                reason="User requested opening youtube website.",
                usage=usage,
            )
        elif "google" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="open_website",
                arguments={"target": "google"},
                reason="User requested opening google website.",
                usage=usage,
            )

        # 4. Match System Info Intent
        elif "system information" in text or "specs" in text or "system info" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="system_information",
                arguments={},
                reason="User requested system information.",
                usage=usage,
            )

        # 5. Match Ambiguous Request -> Clarification
        elif "open project" in text or "open my project" in text:
            return LLMDecision(
                decision_type=DecisionType.CLARIFICATION,
                message="Which project folder would you like me to open?",
                reason="Ambiguous request with multiple matching targets.",
                usage=usage,
            )

        # 6. Conversational / Unsupported Intent
        elif "hello" in text or "hi" in text:
            return LLMDecision(
                decision_type=DecisionType.RESPONSE,
                message="Hello! How can I assist you with your computer today?",
                usage=usage,
            )

        # Default Unsupported
        return LLMDecision(
            decision_type=DecisionType.RESPONSE,
            message="I don't understand that command yet.",
            reason="No tool or intent matched prompt.",
            usage=usage,
        )
