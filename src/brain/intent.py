"""
Intent Recognition System.
Defines abstract interface IntentRecognizer and RuleBasedIntentRecognizer.
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
    """Deterministic, pattern-matching intent recognizer."""

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

        # 1. Conversational Greetings & Questions
        if any(w in text for w in ["hello", "hi ", "hey", "good morning", "how are you", "who are you", "thank you", "thanks"]):
            return Intent(
                intent_type=IntentType.CONVERSATION,
                confidence=1.0,
                parameters={"query": command.raw_text},
                raw_command=command.raw_text,
            )

        # 2. Time & System Information
        if self._matches_system_info(text) or "time is it" in text or "what time" in text or text == "time" or text == "date":
            return Intent(
                intent_type=IntentType.SYSTEM_INFORMATION,
                confidence=1.0,
                parameters={},
                raw_command=command.raw_text,
            )

        # 3. Emergency Stop / Cancel
        if text in ("stop", "stop.", "cancel", "halt", "emergency stop", "pause"):
            return Intent(
                intent_type=IntentType.STOP,
                confidence=1.0,
                parameters={},
                raw_command=command.raw_text,
            )

        # 4. Memory Commands
        if any(text.startswith(w) or f" {w} " in text for w in ["remember", "what do you remember", "recall", "forget"]):
            return Intent(
                intent_type=IntentType.MEMORY,
                confidence=0.95,
                parameters={"query": text},
                raw_command=command.raw_text,
            )

        # 5. Web Search Commands
        if any(text.startswith(w) or f" {w} " in text for w in ["search the web", "search web", "research", "search for"]):
            target = re.sub(r"^(?:search the web for|search web for|search for|research)\s+", "", text).strip()
            return Intent(
                intent_type=IntentType.WEB_SEARCH,
                confidence=0.95,
                parameters={"query": target or text},
                raw_command=command.raw_text,
            )

        # Strip action prefixes like "open", "launch", "start", "show", "run"
        match_open = re.match(r"^(?:open|launch|start|show|run|go to)\s+(.+)$", text)
        target = match_open.group(1).strip() if match_open else text

        # 6. Check explicitly if target is a website URL or website keyword
        if target.startswith(("http://", "https://", "www.")) or target in self.website_keywords:
            return Intent(
                intent_type=IntentType.OPEN_WEBSITE,
                confidence=0.95,
                parameters={"target": target},
                raw_command=command.raw_text,
            )

        # 7. Check if target is a known folder
        if target in self.folder_keywords or any(f in text for f in ["folder", "downloads", "documents", "desktop"]):
            folder_name = "downloads" if "download" in text else ("desktop" if "desktop" in text else ("documents" if "document" in text else target))
            return Intent(
                intent_type=IntentType.OPEN_FOLDER,
                confidence=0.95,
                parameters={"folder_name": folder_name},
                raw_command=command.raw_text,
            )

        # 8. Check if target is a known application
        if target in self.app_keywords or (match_open and any(app in target for app in self.app_keywords)):
            app_name = "calc" if ("calc" in target or "calculator" in target) else ("chrome" if "chrome" in target else ("notepad" if "notepad" in target else target))
            return Intent(
                intent_type=IntentType.OPEN_APPLICATION,
                confidence=0.9,
                parameters={"app_name": app_name},
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
