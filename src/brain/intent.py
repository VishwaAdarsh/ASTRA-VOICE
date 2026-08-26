"""
Intent Recognition System.
Defines abstract interface IntentRecognizer and Phase 1 RuleBasedIntentRecognizer.
"""

from abc import ABC, abstractmethod
import re
from src.brain.models import Command, Intent, IntentType


class IntentRecognizer(ABC):
    """Abstract interface for Intent Recognition engines."""

    @abstractmethod
    def recognize(self, command: Command) -> Intent:
        """Recognize intent from user command."""
        pass


class RuleBasedIntentRecognizer(IntentRecognizer):
    """Deterministic, pattern-matching intent recognizer for Phase 1."""

    def __init__(self):
        # Known folders for disambiguation
        self.folder_keywords = {
            "downloads", "download", "documents", "document", "desktop",
            "pictures", "picture", "photos", "videos", "music", "home"
        }
        # Known website keywords for disambiguation
        self.website_keywords = {
            "youtube", "google", "github", "stackoverflow", "wikipedia", "reddit"
        }
        # Known apps for disambiguation
        self.app_keywords = {
            "calculator", "calc", "notepad", "chrome", "google chrome",
            "vscode", "code", "explorer", "paint", "cmd"
        }

    def recognize(self, command: Command) -> Intent:
        text = command.normalized_text.strip().lower()

        if not text:
            return Intent(intent_type=IntentType.UNKNOWN, confidence=0.0, raw_command=command.raw_text)

        # 1. System Information Intent
        if self._matches_system_info(text):
            return Intent(
                intent_type=IntentType.SYSTEM_INFORMATION,
                confidence=1.0,
                parameters={},
                raw_command=command.raw_text,
            )

        # Strip action prefixes like "open", "launch", "start", "show"
        match_open = re.match(r"^(?:open|launch|start|show|run|go to)\s+(.+)$", text)
        target = match_open.group(1).strip() if match_open else text

        # 2. Check explicitly if target is a website URL or website keyword
        if target.startswith(("http://", "https://", "www.")) or target in self.website_keywords:
            return Intent(
                intent_type=IntentType.OPEN_WEBSITE,
                confidence=0.95,
                parameters={"target": target},
                raw_command=command.raw_text,
            )

        # 3. Check if target is a known folder
        if target in self.folder_keywords:
            return Intent(
                intent_type=IntentType.OPEN_FOLDER,
                confidence=0.95,
                parameters={"folder_name": target},
                raw_command=command.raw_text,
            )

        # 4. Check if target is a known application
        if target in self.app_keywords or match_open:
            # If the user typed "open <x>" and x is not folder/website, treat as app attempt
            if not target.startswith(("http://", "https://")) and "." not in target:
                return Intent(
                    intent_type=IntentType.OPEN_APPLICATION,
                    confidence=0.9,
                    parameters={"app_name": target},
                    raw_command=command.raw_text,
                )

        # Fallback to UNKNOWN
        return Intent(
            intent_type=IntentType.UNKNOWN,
            confidence=0.0,
            parameters={},
            raw_command=command.raw_text,
        )

    def _matches_system_info(self, text: str) -> bool:
        sys_info_patterns = [
            r"^show\s+system\s+information$",
            r"^system\s+information$",
            r"^system\s+info$",
            r"^sysinfo$",
            r"^show\s+system\s+info$",
            r"^specs$",
        ]
        return any(re.match(pattern, text) for pattern in sys_info_patterns)
