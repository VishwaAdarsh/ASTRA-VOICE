"""
ASTRA Context Subsystem Package (Phase 4).
"""

from src.brain.context.conversation import ConversationTurn, Message, Session
from src.brain.context.engine import DesktopContextEngine
from src.brain.context.manager import ContextManager
from src.brain.context.models import (
    ApplicationInfo,
    ClipboardInfo,
    ConfidenceLevel,
    DesktopContextSnapshot,
    DirectoryInfo,
    DisplayInfo,
    FileInfo,
    ScreenInfo,
    UIElementInfo,
    WindowBounds,
    WindowInfo,
)
from src.brain.context.window import ContextWindow

__all__ = [
    "ApplicationInfo",
    "ClipboardInfo",
    "ConfidenceLevel",
    "ContextManager",
    "ContextWindow",
    "ConversationTurn",
    "DesktopContextEngine",
    "DesktopContextSnapshot",
    "DirectoryInfo",
    "DisplayInfo",
    "FileInfo",
    "Message",
    "ScreenInfo",
    "Session",
    "UIElementInfo",
    "WindowBounds",
    "WindowInfo",
]
