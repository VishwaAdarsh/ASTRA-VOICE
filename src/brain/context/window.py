"""
Context Window Truncation and Priority Management.
Ensures context payloads remain within max token limits without dropping core system security instructions.
"""

from src.brain.context.conversation import Message


class ContextWindow:
    """Manages token window truncation and message priority."""

    def __init__(self, max_tokens: int = 2048):
        self.max_tokens = max_tokens

    def truncate_messages(self, messages: list[Message]) -> list[Message]:
        """Truncate message list to fit token window budget while preserving system prompt."""
        if not messages:
            return []

        system_msgs = [m for m in messages if m.role == "system"]
        other_msgs = [m for m in messages if m.role != "system"]

        # Keep recent messages within budget
        budget = self.max_tokens - (len(system_msgs) * 100)
        selected_others = []
        token_count = 0

        for msg in reversed(other_msgs):
            msg_tokens = len(msg.content.split()) * 2  # Approximate token count
            if token_count + msg_tokens > budget:
                break
            selected_others.insert(0, msg)
            token_count += msg_tokens

        return system_msgs + selected_others
