"""
Mock LLM Provider for deterministic offline testing.
Supports Phase 1-5 tool call patterns.
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

        # 1. Open Application Intent
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

        # 3. Memory Tools (Phase 7)
        elif "remember that" in text or "remember i" in text:
            extracted_fact = text.replace("remember that", "").replace("remember", "").strip()
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="remember",
                arguments={"content": extracted_fact or "User preference stored"},
                reason="User requested storing memory.",
                usage=usage,
            )
        elif "forget" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="forget_memory",
                arguments={"target": text.replace("forget", "").strip()},
                reason="User requested deleting memory.",
                usage=usage,
            )
        elif "what do you remember" in text or "show my memories" in text or "list memories" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="list_memories",
                arguments={},
                reason="User requested listing memories.",
                usage=usage,
            )

        # 4. Web Tools (Phase 6)

        elif "search the web" in text or "web search" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="search_web",
                arguments={"query": "Python 3.14 features", "limit": 5},
                reason="User requested web search.",
                usage=usage,
            )
        elif "research" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="research_topic",
                arguments={"topic": "AI Agent Frameworks", "depth": "STANDARD"},
                reason="User requested topic research.",
                usage=usage,
            )
        elif "fetch webpage" in text or "fetch url" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="fetch_webpage",
                arguments={"url": "https://docs.python.org/3.14/"},
                reason="User requested webpage fetch.",
                usage=usage,
            )

        # 5. System Tools (Phase 5)

        elif "find" in text or "search" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="search_files",
                arguments={"query": "report", "location": "Downloads"},
                reason="User requested file search.",
                usage=usage,
            )
        elif "create a folder" in text or "create folder" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="create_folder",
                arguments={"folder_name": "AI Research", "location": "Desktop"},
                reason="User requested folder creation.",
                usage=usage,
            )
        elif "create text file" in text or "create file" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="create_text_file",
                arguments={"filename": "report.txt", "content": "Hello ASTRA", "location": "Documents"},
                reason="User requested text file creation.",
                usage=usage,
            )
        elif "rename" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="rename_file",
                arguments={"source": "report.pdf", "new_name": "final_report.pdf"},
                reason="User requested file rename.",
                usage=usage,
            )
        elif "move" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="move_file",
                arguments={"source": "report.pdf", "destination": "Documents"},
                reason="User requested moving file.",
                usage=usage,
            )
        elif "copy" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="copy_file",
                arguments={"source": "report.pdf", "destination": "Desktop"},
                reason="User requested file copy.",
                usage=usage,
            )
        elif "delete" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="delete_file",
                arguments={"target": "old_report.pdf"},
                reason="User requested safe file deletion.",
                usage=usage,
            )
        elif "organize" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="organize_folder",
                arguments={"folder": "Downloads", "dry_run": True},
                reason="User requested folder organization preview.",
                usage=usage,
            )
        elif "downloads" in text or "download" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="open_folder",
                arguments={"folder_name": "downloads"},
                reason="User requested opening downloads folder.",
                usage=usage,
            )

        # 3. Applications & Projects (Phase 5)
        elif "close" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="close_application",
                arguments={"app_name": "calculator"},
                reason="User requested closing application.",
                usage=usage,
            )
        # 5. Conversational / Ambiguous
        elif "open my project" in text:
            return LLMDecision(
                decision_type=DecisionType.CLARIFICATION,
                message="Which project folder would you like me to open?",
                reason="Ambiguous request with multiple matching targets.",
                usage=usage,
            )
        elif "project" in text and ("ip" in text or "astra" in text):
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="open_project",
                arguments={"project_name": "ASTRA-VOICE"},
                reason="User requested opening project.",
                usage=usage,
            )

        elif "doing" in text or "how is my computer" in text or "resources" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="resource_information",
                arguments={},
                reason="User requested system resource status.",
                usage=usage,
            )
        elif "screenshot" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="screenshot",
                arguments={},
                reason="User requested screenshot capture.",
                usage=usage,
            )
        elif "volume" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="volume_control",
                arguments={"action": "up"},
                reason="User requested volume control.",
                usage=usage,
            )
        elif "youtube" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="open_website",
                arguments={"target": "youtube"},
                reason="User requested opening youtube website.",
                usage=usage,
            )
        elif "system information" in text or "specs" in text:
            return LLMDecision(
                decision_type=DecisionType.TOOL_CALL,
                tool_name="system_information",
                arguments={},
                reason="User requested system information.",
                usage=usage,
            )

        # 5. Conversational / Ambiguous
        elif "open my project" in text:
            return LLMDecision(
                decision_type=DecisionType.CLARIFICATION,
                message="Which project folder would you like me to open?",
                reason="Ambiguous request with multiple matching targets.",
                usage=usage,
            )
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
