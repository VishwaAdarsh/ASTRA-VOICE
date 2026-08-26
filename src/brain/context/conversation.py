"""
Conversation Context Tracking Models.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Message:
    """Single conversational message."""

    role: str  # 'system', 'user', 'assistant', 'tool'
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationTurn:
    """Complete interaction turn (User command + LLM Decision + Tool Result + Final Response)."""

    user_message: Message
    assistant_message: Message | None = None
    tool_name: str | None = None
    tool_result_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Session:
    """Active conversational session data container."""

    session_id: str = "default_session"
    turns: list[ConversationTurn] = field(default_factory=list)
    active_task: str | None = None
