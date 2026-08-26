"""
Application Alias Registry.
Maps human aliases (e.g. 'code', 'vscode', 'chrome', 'calculator') to verified executables.
"""

from typing import Any
from src.core.config import Config


class ApplicationRegistry:
    """Manages application alias mapping and executable resolution."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.aliases: dict[str, str] = {
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "notepad": "notepad.exe",
            "chrome": "chrome.exe",
            "google chrome": "chrome.exe",
            "browser": "chrome.exe",
            "vscode": "code",
            "code": "code",
            "visual studio code": "code",
            "explorer": "explorer.exe",
            "file explorer": "explorer.exe",
            "paint": "mspaint.exe",
            "cmd": "cmd.exe",
            "terminal": "cmd.exe",
        }

    def resolve_executable(self, app_name: str) -> str | None:
        """Resolve application alias to executable command."""
        cleaned = app_name.lower().strip()
        if cleaned in self.aliases:
            return self.aliases[cleaned]
        return self.config.get_app_executable(cleaned)
