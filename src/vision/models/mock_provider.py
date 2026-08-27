"""
Mock Vision Provider for deterministic unit testing and offline execution.
"""

from src.vision.models import Screenshot
from src.vision.models.provider import VisionProvider


class MockVisionProvider(VisionProvider):
    """Mock Vision Provider returning structured visual analysis text."""

    def analyze(self, screenshot: Screenshot, ocr_text: str = "") -> str:
        title = (screenshot.window_title or "").lower()

        if "syntaxerror" in ocr_text.lower() or "error" in ocr_text.lower():
            return "Active window shows VS Code with a Python SyntaxError visible in the terminal output."
        elif "code" in title or "astra" in title:
            return "Active window is VS Code displaying the ASTRA assistant codebase."
        elif "chrome" in title or "browser" in title:
            return "Active window is Google Chrome browser displaying documentation."
        else:
            return f"Desktop screen displaying active application '{screenshot.app_name or 'Windows Application'}'."
