"""
Desktop Context Collectors.
Modular, robust collectors for Windows active window, process, multi-monitor display,
active document/file, working directory, privacy-gated clipboard, and request-driven screen context.
"""

import ctypes
import ctypes.wintypes
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Optional

from src.brain.context.models import (
    ApplicationInfo,
    ClipboardInfo,
    ConfidenceLevel,
    DirectoryInfo,
    DisplayInfo,
    FileInfo,
    ScreenInfo,
    UIElementInfo,
    WindowBounds,
    WindowInfo,
)
from src.core.config import Config
from src.core.logger import get_logger
from src.security.auditor import SecretRedactionFilter
from src.tools.applications.aliases import ApplicationRegistry

logger = get_logger()

# Windows API Constants
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MONITOR_DEFAULTTONEAREST = 0x00000002
SM_CXSCREEN = 0
SM_CYSCREEN = 1
SM_CMONITORS = 80
CF_UNICODETEXT = 13


class ActiveWindowCollector:
    """Collects foreground window handle, title, bounding rectangle, and window state."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def collect(self) -> WindowInfo | None:
        """Query Windows user32 for foreground window information."""
        if sys.platform != "win32":
            return None

        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return None

            # 1. Window Title
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.strip()
            else:
                title = "Untitled Window"

            # 2. Window Bounds
            bounds = None
            try:
                rect = ctypes.wintypes.RECT()
                if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                    bounds = WindowBounds(
                        left=rect.left,
                        top=rect.top,
                        right=rect.right,
                        bottom=rect.bottom,
                    )
            except Exception:
                bounds = None

            # 3. Window State
            is_minimized = bool(user32.IsIconic(hwnd))
            is_maximized = bool(user32.IsZoomed(hwnd))

            return WindowInfo(
                hwnd=hwnd,
                title=title,
                bounds=bounds,
                is_minimized=is_minimized,
                is_maximized=is_maximized,
                source="windows_user32",
            )
        except Exception as e:
            logger.debug(f"ActiveWindowCollector error: {e}")
            return None


class ProcessCollector:
    """Resolves process ID, executable path, and normalized application identity."""

    def __init__(self, config: Config | None = None, app_registry: ApplicationRegistry | None = None):
        self.config = config or Config()
        self.app_registry = app_registry or ApplicationRegistry(config=self.config)

    def _get_process_id(self, hwnd: int) -> int | None:
        """Query process ID from window handle."""
        try:
            pid = ctypes.wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            return pid.value if pid.value > 0 else None
        except Exception:
            return None

    def _get_process_path(self, process_id: int) -> str:
        """Query executable path from process ID."""
        try:
            kernel32 = ctypes.windll.kernel32
            h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, process_id)
            if h_proc:
                try:
                    size = ctypes.wintypes.DWORD(1024)
                    buf = ctypes.create_unicode_buffer(size.value)
                    if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size)):
                        return buf.value
                finally:
                    kernel32.CloseHandle(h_proc)
        except Exception as e:
            logger.debug(f"ProcessCollector OpenProcess error: {e}")
        return ""

    def collect(self, hwnd: int | None, window_title: str = "") -> ApplicationInfo | None:
        """Resolve process metadata from window handle and title."""
        if not hwnd or sys.platform != "win32":
            return None

        process_id = self._get_process_id(hwnd)
        executable_path = self._get_process_path(process_id) if process_id else ""
        process_name = Path(executable_path).name if executable_path else ""

        # Normalize application identity using ApplicationRegistry
        app_id = "unknown"
        display_name = process_name or "Unknown Application"
        is_known = False

        APP_DISPLAY_NAMES = {
            "vscode": "Visual Studio Code",
            "code": "Visual Studio Code",
            "chrome": "Google Chrome",
            "calculator": "Calculator",
            "notepad": "Notepad",
            "explorer": "File Explorer",
            "paint": "Paint",
            "cmd": "Command Prompt",
        }

        if process_name:
            exe_lower = process_name.lower()
            # Check against known aliases
            for alias, target_exe in self.app_registry.aliases.items():
                if exe_lower == target_exe.lower() or exe_lower == f"{target_exe.lower()}.exe":
                    app_id = alias
                    display_name = APP_DISPLAY_NAMES.get(alias, alias.title())
                    is_known = True
                    break

        # Fallback to window title clues if process_name was empty or unrecognized
        if not is_known and window_title:
            title_lower = window_title.lower()
            if "visual studio code" in title_lower or " — astra" in title_lower or "code" in title_lower:
                app_id = "vscode"
                display_name = "Visual Studio Code"
                process_name = process_name or "Code.exe"
                is_known = True
            elif "google chrome" in title_lower or "chrome" in title_lower:
                app_id = "chrome"
                display_name = "Google Chrome"
                process_name = process_name or "chrome.exe"
                is_known = True
            elif "file explorer" in title_lower:
                app_id = "explorer"
                display_name = "File Explorer"
                process_name = process_name or "explorer.exe"
                is_known = True
            elif "notepad" in title_lower:
                app_id = "notepad"
                display_name = "Notepad"
                process_name = process_name or "notepad.exe"
                is_known = True

        return ApplicationInfo(
            app_id=app_id,
            name=display_name,
            executable=process_name or executable_path,
            process_id=process_id,
            is_known=is_known,
            source="windows_process",
        )


class DisplayCollector:
    """Collects multi-monitor display metrics and bounds for active and primary displays."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def collect(self, hwnd: int | None = None) -> DisplayInfo:
        """Query Windows system metrics for display configuration."""
        if sys.platform != "win32":
            return DisplayInfo()

        try:
            user32 = ctypes.windll.user32
            monitor_count = user32.GetSystemMetrics(SM_CMONITORS) or 1
            primary_width = user32.GetSystemMetrics(SM_CXSCREEN) or 1920
            primary_height = user32.GetSystemMetrics(SM_CYSCREEN) or 1080

            primary_bounds = WindowBounds(left=0, top=0, right=primary_width, bottom=primary_height)
            active_bounds = primary_bounds
            is_primary = True

            if hwnd:
                h_monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
                if h_monitor:
                    # MONITORINFO struct: cbSize, rcMonitor (RECT), rcWork (RECT), dwFlags
                    class MONITORINFO(ctypes.Structure):
                        _fields_ = [
                            ("cbSize", ctypes.wintypes.DWORD),
                            ("rcMonitor", ctypes.wintypes.RECT),
                            ("rcWork", ctypes.wintypes.RECT),
                            ("dwFlags", ctypes.wintypes.DWORD),
                        ]

                    info = MONITORINFO()
                    info.cbSize = ctypes.sizeof(MONITORINFO)
                    if user32.GetMonitorInfoW(h_monitor, ctypes.byref(info)):
                        active_bounds = WindowBounds(
                            left=info.rcMonitor.left,
                            top=info.rcMonitor.top,
                            right=info.rcMonitor.right,
                            bottom=info.rcMonitor.bottom,
                        )
                        is_primary = bool(info.dwFlags & 1)  # MONITORINFOF_PRIMARY = 1

            return DisplayInfo(
                monitor_count=monitor_count,
                active_display_bounds=active_bounds,
                primary_display_bounds=primary_bounds,
                is_primary=is_primary,
                source="windows_display",
            )
        except Exception as e:
            logger.debug(f"DisplayCollector error: {e}")
            return DisplayInfo()


class FileContextCollector:
    """
    Safely infers the active document or file from window titles and application metadata.
    IMPORTANT: Never fabricates an absolute path when only a filename is known.
    """

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def collect(self, app_info: ApplicationInfo | None, window_title: str) -> FileInfo | None:
        """Infer active document from application context and window title."""
        if not window_title or not app_info:
            return None

        app_id = app_info.app_id.lower()
        title = window_title.strip()

        # 1. Visual Studio Code
        # Patterns: "filename.py — ProjectName — Visual Studio Code" or "filename.py - Visual Studio Code" or "● filename.py"
        if app_id == "vscode" or "visual studio code" in title.lower():
            clean_title = title.replace("● ", "")  # Unsaved indicator
            parts = [p.strip() for p in re.split(r"[\u2014\-]", clean_title)]
            if parts and parts[0]:
                file_name = parts[0]
                # Filter out generic titles like "Visual Studio Code" or "Get Started"
                if file_name.lower() not in ("visual studio code", "get started", "welcome", "settings"):
                    return FileInfo(
                        name=file_name,
                        path=None,  # Path is unknown; do NOT fabricate
                        confidence=ConfidenceLevel.INFERRED,
                        source="vscode_window_title",
                    )

        # 2. Notepad
        # Pattern: "filename.txt - Notepad" or "*filename.txt - Notepad"
        if app_id == "notepad" or "notepad" in title.lower():
            clean_title = title.lstrip("*").strip()
            parts = clean_title.split(" - Notepad")
            if parts and parts[0]:
                file_name = parts[0].strip()
                if file_name.lower() != "notepad":
                    return FileInfo(
                        name=file_name,
                        path=None,
                        confidence=ConfidenceLevel.INFERRED,
                        source="notepad_window_title",
                    )

        # 3. Microsoft Office (Word / Excel / PowerPoint)
        for office_app in ("word", "excel", "powerpoint"):
            if office_app in title.lower():
                parts = title.split(f" - {office_app.title()}")
                if parts and parts[0]:
                    return FileInfo(
                        name=parts[0].strip(),
                        path=None,
                        confidence=ConfidenceLevel.INFERRED,
                        source=f"{office_app}_window_title",
                    )

        # 4. Adobe Acrobat / PDF Reader
        if "acrobat" in title.lower() or "pdf" in title.lower():
            parts = re.split(r"[\u2014\-]", title)
            for part in parts:
                candidate = part.strip()
                if candidate.lower().endswith(".pdf"):
                    return FileInfo(
                        name=candidate,
                        path=None,
                        confidence=ConfidenceLevel.INFERRED,
                        source="pdf_window_title",
                    )

        return None


class DirectoryContextCollector:
    """
    Safely infers the active directory from Explorer windows or known workspace directories.
    Distinguishes clearly between process working directory and user's active Explorer folder.
    """

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def collect(self, app_info: ApplicationInfo | None, window_title: str) -> DirectoryInfo | None:
        """Infer current folder from Explorer window title or allowlisted folders."""
        if not window_title or not app_info:
            return None

        app_id = app_info.app_id.lower()
        title = window_title.strip()

        # File Explorer
        if app_id == "explorer" or "file explorer" in title.lower() or title.lower() == "explorer":
            folder_name = title.replace("File Explorer", "").strip() or "Explorer"

            # Check if title matches a known safe allowlisted folder
            cleaned = folder_name.lower().strip()
            if cleaned in self.config.folder_allowlist:
                known_path = str(self.config.folder_allowlist[cleaned])
                return DirectoryInfo(
                    name=folder_name,
                    path=known_path,
                    confidence=ConfidenceLevel.INFERRED,
                    source="explorer_allowlist_match",
                )

            # Check if title looks like an absolute path (e.g. C:\Projects\ASTRA)
            if re.match(r"^[a-zA-Z]:\\", folder_name):
                return DirectoryInfo(
                    name=Path(folder_name).name or folder_name,
                    path=folder_name if Path(folder_name).exists() else None,
                    confidence=ConfidenceLevel.EXACT if Path(folder_name).exists() else ConfidenceLevel.INFERRED,
                    source="explorer_path_title",
                )

            return DirectoryInfo(
                name=folder_name,
                path=None,  # Path cannot be safely proven
                confidence=ConfidenceLevel.INFERRED,
                source="explorer_window_title",
            )

        return None


class ClipboardCollector:
    """
    Read-only, privacy-conscious clipboard inspector.
    Clipboard content is NEVER automatically exposed unless explicitly requested.
    All text is passed through SecretRedactionFilter to strip tokens/passwords.
    """

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def collect(self, explicit_requested: bool = False) -> ClipboardInfo:
        """
        Inspect clipboard.
        If explicit_requested is False, returns availability status without reading content.
        If explicit_requested is True, reads text, sanitizes secrets, and returns text preview.
        """
        if sys.platform != "win32":
            return ClipboardInfo(available=False, content_type="none")

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        try:
            # Check availability without locking or holding clipboard
            has_text = bool(user32.IsClipboardFormatAvailable(CF_UNICODETEXT))
            if not has_text:
                return ClipboardInfo(available=False, content_type="none")

            if not explicit_requested:
                # Privacy-safe: report availability without extracting content
                return ClipboardInfo(
                    available=True,
                    content_type="text",
                    text_preview=None,
                    is_redacted=False,
                    source="windows_clipboard",
                )

            # Explicit request: open clipboard, extract text, redact secrets
            if not user32.OpenClipboard(None):
                return ClipboardInfo(available=True, content_type="text", text_preview=None)

            try:
                h_clip = user32.GetClipboardData(CF_UNICODETEXT)
                if not h_clip:
                    return ClipboardInfo(available=True, content_type="text", text_preview=None)

                p_clip = kernel32.GlobalLock(h_clip)
                if not p_clip:
                    return ClipboardInfo(available=True, content_type="text", text_preview=None)

                try:
                    raw_text = ctypes.c_wchar_p(p_clip).value or ""
                finally:
                    kernel32.GlobalUnlock(h_clip)
            finally:
                user32.CloseClipboard()

            # Redact secrets
            redacted_text = SecretRedactionFilter.redact(raw_text)
            was_redacted = redacted_text != raw_text

            # Limit preview length for safety
            preview = redacted_text[:500] + ("..." if len(redacted_text) > 500 else "")

            return ClipboardInfo(
                available=True,
                content_type="text",
                text_preview=preview,
                is_redacted=was_redacted,
                source="windows_clipboard",
            )
        except Exception as e:
            logger.debug(f"ClipboardCollector error: {e}")
            return ClipboardInfo(available=False, content_type="none")


class FocusedElementCollector:
    """Collects accessibility UI control element information with graceful fallback."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def collect(self, hwnd: int | None = None) -> UIElementInfo | None:
        """Inspect focused UI control via Windows accessibility or return None gracefully."""
        # Safe interface: establish data structure without destabilizing runtime
        return None


class ScreenCollector:
    """Collects visual screen capture metadata on-demand via VisionManager."""

    def __init__(self, config: Config | None = None, vision_manager: Any = None):
        self.config = config or Config()
        self.vision_manager = vision_manager

    def collect(self, explicit_requested: bool = False) -> ScreenInfo:
        """
        Capture screen ONLY when explicitly requested by user or capability.
        Returns ScreenInfo metadata.
        """
        if not explicit_requested or not self.vision_manager:
            return ScreenInfo(available=True, captured=False)

        try:
            context = self.vision_manager.analyze_screen()
            return ScreenInfo(
                available=True,
                captured=True,
                screenshot_path=getattr(context.screenshot, "file_path", None),
                description=context.description,
                source="vision_screen_on_demand",
            )
        except Exception as e:
            logger.debug(f"ScreenCollector on-demand capture error: {e}")
            return ScreenInfo(available=True, captured=False)
