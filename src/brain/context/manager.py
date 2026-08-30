"""
Context Manager Subsystem.
Orchestrates conversation history, recent tool results, and LLM context payload formatting.
"""

from src.brain.context.conversation import ConversationTurn, Message, Session
from src.brain.context.window import ContextWindow
from src.core.logger import get_logger

logger = get_logger()


class ContextManager:
    """Manages conversational state and context payload construction."""

    def __init__(self, max_tokens: int = 2048):
        self.session = Session()
        self.window = ContextWindow(max_tokens=max_tokens)

    def add_user_message(self, text: str) -> Message:
        """Add user input message to active context session."""
        msg = Message(role="user", content=text)
        turn = ConversationTurn(user_message=msg)
        self.session.turns.append(turn)
        logger.info(f"CONTEXT: Added user message '{text}' (session_turns={len(self.session.turns)})")
        return msg

    def record_turn_result(self, response_text: str, tool_name: str | None = None, tool_data: dict | None = None) -> None:
        """Record completed turn result in active context session."""
        if not self.session.turns:
            return

        last_turn = self.session.turns[-1]
        last_turn.assistant_message = Message(role="assistant", content=response_text)
        last_turn.tool_name = tool_name
        last_turn.tool_result_data = tool_data or {}

    def get_formatted_context_prompt(self) -> str:
        """Build formatted conversation history string for the LLM."""
        lines = []
        # Include past completed turns (excluding current in-flight turn if without assistant message)
        completed_turns = [t for t in self.session.turns if t.assistant_message]
        recent_turns = completed_turns[-5:]
        for turn in recent_turns:
            lines.append(f"User: {turn.user_message.content}")
            if turn.assistant_message:
                lines.append(f"ASTRA: {turn.assistant_message.content}")
            if turn.tool_name:
                lines.append(f"Tool executed: {turn.tool_name}")

        return "\n".join(lines) if lines else "None (New Session)"


    def clear(self) -> None:
        """Clear active session context history."""
        self.session.turns.clear()
        self.session.active_task = None
