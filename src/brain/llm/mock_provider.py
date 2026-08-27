"""
Mock LLM Provider for deterministic offline testing.
Supports Phase 1-8 tool call patterns.
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

        # Extract current request text from full context prompt
        if "Current Request:" in prompt:
            req_text = prompt.split("Current Request:")[-1].strip().lower()
        else:
            req_text = prompt.strip().lower()

        usage = LLMUsage(
            prompt_tokens=len(prompt.split()),
            completion_tokens=15,
            total_tokens=len(prompt.split()) + 15,
            latency_ms=(time.time() - start_time) * 1000,
        )

        # 1. Greetings & Stop & Time
        if any(w in req_text for w in ["hello", "hi ", "hey", "good morning", "how are you"]):
            return LLMDecision(
                decision_type=DecisionType.RESPONSE,
                message="Hello! I am ASTRA, your personal AI computer assistant. How can I help you today?",
                usage=usage,
            )

        if "what time" in req_text or "time is it" in req_text or req_text == "time":
            return LLMDecision(
                decision_type=DecisionType.RESPONSE,
                message=f"The current local time is {time.strftime('%I:%M %p')}.",
                usage=usage,
            )

        if req_text in ("stop", "stop.", "cancel", "halt", "emergency stop"):
            return LLMDecision(
                decision_type=DecisionType.RESPONSE,
                message="Stopped active operations.",
                usage=usage,
            )

        # 2. Memory Tools (Phase 7)
        if "remember that" in req_text or "remember i" in req_text or req_text.startswith("remember "):
            extracted_fact = req_text.split("remember", 1)[-1].replace("that", "").strip()
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="remember",
                arguments={"content": extracted_fact or "User preference stored"},
                reason="User requested storing memory.",
                usage=usage,
            )
        elif "what do you remember" in req_text or "recall" in req_text or "show my memories" in req_text or "list memories" in req_text:
            q = req_text.replace("what do you remember about", "").replace("what do you remember", "").strip()
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="retrieve_memory",
                arguments={"query": q or "project"},
                reason="User requested memory retrieval.",
                usage=usage,
            )
        elif "forget" in req_text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="forget_memory",
                arguments={"target": req_text.replace("forget", "").strip()},
                reason="User requested deleting memory.",
                usage=usage,
            )

        # 3. Web Intelligence & Search Tools (Phase 6)
        if "search the web" in req_text or "web search" in req_text or "search for" in req_text:
            query_str = req_text.replace("search the web for", "").replace("search web for", "").replace("search for", "").strip()
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="search_web",
                arguments={"query": query_str or "latest AI news", "limit": 5},
                reason="User requested web search.",
                usage=usage,
            )
        elif "research" in req_text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="research_topic",
                arguments={"topic": "AI Agent Frameworks", "depth": "STANDARD"},
                reason="User requested topic research.",
                usage=usage,
            )
        elif "fetch webpage" in req_text or "fetch url" in req_text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="fetch_webpage",
                arguments={"url": "https://docs.python.org/3.14/"},
                reason="User requested webpage fetch.",
                usage=usage,
            )

        # 4. Open Application & Folders (Phase 1, 5)
        if "downloads" in req_text or "download folder" in req_text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="open_folder",
                arguments={"folder_name": "downloads"},
                reason="User requested opening downloads folder.",
                usage=usage,
            )
        elif "calculator" in req_text or "calc" in req_text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="open_application",
                arguments={"app_name": "calculator"},
                reason="User requested opening calculator application.",
                usage=usage,
            )
        elif "notepad" in req_text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="open_application",
                arguments={"app_name": "notepad"},
                reason="User requested opening notepad application.",
                usage=usage,
            )
        elif "chrome" in req_text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="open_application",
                arguments={"app_name": "chrome"},
                reason="User requested opening chrome application.",
                usage=usage,
            )

        # 5. Vision Tools (Phase 8)
        elif "look at my screen" in req_text or "what is on my screen" in req_text or "analyze screen" in req_text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="analyze_screen",
                arguments={},
                reason="User requested desktop screen visual analysis.",
                usage=usage,
            )
        elif "active window" in req_text or "what application is open" in req_text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="analyze_active_window",
                arguments={},
                reason="User requested active window visual analysis.",
                usage=usage,
            )

        # Default Response
        return LLMDecision(
            decision_type=DecisionType.RESPONSE,
            message="I processed your request and updated the assistant context.",
            reason="Processed conversational command.",
            usage=usage,
        )
