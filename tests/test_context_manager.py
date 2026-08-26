"""
Unit tests for ContextManager and ContextWindow truncation.
"""

from src.brain.context.conversation import Message
from src.brain.context.manager import ContextManager
from src.brain.context.window import ContextWindow


def test_context_manager_add_and_record():
    cm = ContextManager()
    cm.add_user_message("Open Chrome")
    cm.record_turn_result("Chrome is open.", tool_name="open_application", tool_data={"app_name": "chrome"})

    assert len(cm.session.turns) == 1
    turn = cm.session.turns[0]
    assert turn.user_message.content == "Open Chrome"
    assert turn.assistant_message.content == "Chrome is open."
    assert turn.tool_name == "open_application"

    formatted = cm.get_formatted_context_prompt()
    assert "User: Open Chrome" in formatted
    assert "ASTRA: Chrome is open." in formatted


def test_context_window_truncation():
    cw = ContextWindow(max_tokens=100)
    messages = [
        Message(role="system", content="System instruction"),
        Message(role="user", content="Old message 1 " * 20),
        Message(role="user", content="Old message 2 " * 20),
        Message(role="user", content="Recent message"),
    ]

    truncated = cw.truncate_messages(messages)
    assert len(truncated) < len(messages)
    assert truncated[0].role == "system"  # System instruction preserved
