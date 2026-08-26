"""
Response Prompt Templates.
"""


def format_clarification_question(options: list[str]) -> str:
    """Format structured clarification prompt."""
    bullet_list = "\n".join([f"  - {opt}" for opt in options])
    return f"Which one did you mean?\n{bullet_list}"
