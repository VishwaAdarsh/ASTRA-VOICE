import os
import shutil
from typing import Any
from src.core.config import Config


KNOWN_APP_PATHS: dict[str, list[str]] = {
    "chrome.exe": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
    ],
    "msedge.exe": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe"),
    ],
    "code": [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
        r"C:\Program Files\Microsoft VS Code\Code.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\bin\code.cmd"),
    ],
    "brave.exe": [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
    ],
}


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
            "edge": "msedge.exe",
            "microsoft edge": "msedge.exe",
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
        """Resolve application alias to executable command or full path."""
        cleaned = app_name.lower().strip()
        cmd = self.aliases.get(cleaned) or self.config.get_app_executable(cleaned)
        if not cmd:
            return None

        # If already an existing full path or found on PATH, return it
        if os.path.exists(cmd) or shutil.which(cmd):
            return cmd

        # Check known installation paths
        for path in KNOWN_APP_PATHS.get(cmd, []):
            if os.path.exists(path):
                return path

        return cmd
