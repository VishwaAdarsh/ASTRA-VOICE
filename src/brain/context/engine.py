"""
Desktop Context Engine.
Orchestrates context collectors, enforces freshness and short-lived caching,
filters task-relevant context for LLM requests, and wraps untrusted desktop data
with prompt-injection defense.
"""

import threading
import time
from typing import Any, Optional

from src.brain.context.collectors import (
    ActiveWindowCollector,
    ClipboardCollector,
    DirectoryContextCollector,
    DisplayCollector,
    FileContextCollector,
    FocusedElementCollector,
    ProcessCollector,
    ScreenCollector,
)
from src.brain.context.models import DesktopContextSnapshot
from src.core.config import Config
from src.core.logger import get_logger
from src.security.injection import PromptInjectionDefense

logger = get_logger()


class DesktopContextEngine:
    """
    Central coordinator for Windows desktop context collection.
    Provides coherent, fresh snapshots and task-relevant context filtering for the Agent.
    """

    def __init__(
        self,
        config: Config | None = None,
        vision_manager: Any = None,
        injection_defense: PromptInjectionDefense | None = None,
    ):
        self.config = config or Config()
        self.enabled = getattr(self.config, "desktop_context_enabled", True)
        self.cache_ttl = getattr(self.config, "context_cache_ttl_seconds", 0.5)

        # Initialize modular collectors
        self.active_window_collector = ActiveWindowCollector(config=self.config)
        self.process_collector = ProcessCollector(config=self.config)
        self.display_collector = DisplayCollector(config=self.config)
        self.file_collector = FileContextCollector(config=self.config)
        self.directory_collector = DirectoryContextCollector(config=self.config)
        self.clipboard_collector = ClipboardCollector(config=self.config)
        self.focused_element_collector = FocusedElementCollector(config=self.config)
        self.screen_collector = ScreenCollector(config=self.config, vision_manager=vision_manager)

        self.injection_defense = injection_defense or PromptInjectionDefense(config=self.config)

        self._cached_snapshot: DesktopContextSnapshot | None = None
        self._lock = threading.Lock()

    def get_current_context(
        self,
        force_refresh: bool = False,
        include_clipboard: bool = False,
        include_screen: bool = False,
    ) -> DesktopContextSnapshot:
        """
        Assemble and return a coherent DesktopContextSnapshot.
        Uses short-lived caching for fast metadata (active window, process, display).
        Clipboard and screen captures are strictly request-driven.
        """
        if not self.enabled:
            return DesktopContextSnapshot()

        with self._lock:
            # Check cache validity if no explicit heavyweight data is requested
            if not force_refresh and not include_clipboard and not include_screen:
                if self._cached_snapshot and not self._cached_snapshot.is_stale(self.cache_ttl):
                    return self._cached_snapshot

            t0 = time.time()

            # 1. Active Window
            try:
                window_info = self.active_window_collector.collect()
            except Exception as e:
                logger.debug(f"ActiveWindowCollector failure: {e}")
                window_info = None

            hwnd = window_info.hwnd if window_info else None
            window_title = window_info.title if window_info else ""

            # 2. Process & Application
            try:
                app_info = self.process_collector.collect(hwnd=hwnd, window_title=window_title)
            except Exception as e:
                logger.debug(f"ProcessCollector failure: {e}")
                app_info = None

            # 3. Display Metrics
            try:
                display_info = self.display_collector.collect(hwnd=hwnd)
            except Exception as e:
                logger.debug(f"DisplayCollector failure: {e}")
                display_info = None

            # 4. Inferred File / Document
            try:
                file_info = self.file_collector.collect(app_info=app_info, window_title=window_title)
            except Exception as e:
                logger.debug(f"FileContextCollector failure: {e}")
                file_info = None

            # 5. Inferred Directory
            try:
                directory_info = self.directory_collector.collect(app_info=app_info, window_title=window_title)
            except Exception as e:
                logger.debug(f"DirectoryContextCollector failure: {e}")
                directory_info = None

            # 6. Clipboard (privacy-gated)
            try:
                clipboard_info = self.clipboard_collector.collect(explicit_requested=include_clipboard)
            except Exception as e:
                logger.debug(f"ClipboardCollector failure: {e}")
                clipboard_info = None

            # 7. Focused UI Element
            try:
                ui_element = self.focused_element_collector.collect(hwnd=hwnd)
            except Exception as e:
                logger.debug(f"FocusedElementCollector failure: {e}")
                ui_element = None

            # 8. Screen Context (request-driven)
            try:
                screen_info = self.screen_collector.collect(explicit_requested=include_screen)
            except Exception as e:
                logger.debug(f"ScreenCollector failure: {e}")
                screen_info = None

            elapsed_ms = (time.time() - t0) * 1000.0

            snapshot = DesktopContextSnapshot(
                timestamp=time.time(),
                active_window=window_info,
                active_application=app_info,
                display=display_info,
                active_file=file_info,
                current_directory=directory_info,
                clipboard=clipboard_info,
                focused_element=ui_element,
                screen=screen_info,
                metadata={
                    "latency_ms": round(elapsed_ms, 2),
                    "sources": {
                        "window": getattr(window_info, "source", None),
                        "application": getattr(app_info, "source", None),
                        "display": getattr(display_info, "source", None),
                        "file": getattr(file_info, "source", None),
                        "directory": getattr(directory_info, "source", None),
                        "clipboard": getattr(clipboard_info, "source", None),
                    },
                },
            )

            # Update cache if this was a standard metadata collection
            if not include_clipboard and not include_screen:
                self._cached_snapshot = snapshot

            return snapshot

    def get_relevant_context(self, user_command: str) -> str:
        """
        Filter task-relevant desktop context for a user command, apply prompt-injection
        sanitization, and format into a structured prompt section.
        """
        if not self.enabled or not user_command:
            return ""

        cmd_lower = user_command.lower()

        # Determine explicit capability triggers
        wants_screen = any(w in cmd_lower for w in ["screen", "look at", "what do you see", "on my display", "visible"])
        wants_clipboard = any(w in cmd_lower for w in ["clipboard", "copied", "paste", "what did i copy"])
        wants_file = any(w in cmd_lower for w in ["file", "editing", "document", "code", "script", "what am i working on"])
        wants_directory = any(w in cmd_lower for w in ["folder", "directory", "where am i", "path", "cwd"])
        wants_window = any(w in cmd_lower for w in ["this", "close this", "minimize", "maximize", "active window", "what app", "current app", "focused"])

        # Collect snapshot with appropriate flags
        snapshot = self.get_current_context(
            force_refresh=False,
            include_clipboard=wants_clipboard,
            include_screen=wants_screen,
        )

        lines: list[str] = []

        # 1. Active Application & Window (included for window-targeted commands or general context)
        if snapshot.active_application:
            app = snapshot.active_application
            lines.append(f"Active Application: {app.name} (id: {app.app_id}, process: {app.executable or 'unknown'})")

        if snapshot.active_window and (wants_window or wants_file or wants_screen or "this" in cmd_lower):
            # Sanitize window title as untrusted input
            raw_title = snapshot.active_window.title
            safe_title = self.injection_defense.sanitize_untrusted_data(raw_title, source_tag="WINDOW_TITLE")
            lines.append(f"Active Window Title: {safe_title}")

        # 2. Inferred File / Document
        if snapshot.active_file and (wants_file or "this" in cmd_lower):
            file_name = self.injection_defense.sanitize_untrusted_data(snapshot.active_file.name, source_tag="ACTIVE_FILE")
            lines.append(f"Active Document: {file_name} (Confidence: {snapshot.active_file.confidence.value})")

        # 3. Current Directory
        if snapshot.current_directory and (wants_directory or "here" in cmd_lower):
            dir_name = snapshot.current_directory.name
            dir_path = snapshot.current_directory.path or "[Path not determinable]"
            lines.append(f"Current Directory: {dir_name} (Path: {dir_path})")

        # 4. Clipboard (only if explicitly requested and available)
        if wants_clipboard and snapshot.clipboard and snapshot.clipboard.text_preview:
            safe_clipboard = self.injection_defense.sanitize_untrusted_data(
                snapshot.clipboard.text_preview, source_tag="CLIPBOARD_CONTENT"
            )
            redacted_note = " [Credentials Redacted]" if snapshot.clipboard.is_redacted else ""
            lines.append(f"Clipboard Text{redacted_note}:\n{safe_clipboard}")

        # 5. Screen Context (only if explicitly requested and captured)
        if wants_screen and snapshot.screen and snapshot.screen.captured:
            lines.append(f"Visual Screen Description: {snapshot.screen.description or 'Screen image captured'}")

        # 6. Multi-Monitor Display
        if wants_screen or "monitor" in cmd_lower or "display" in cmd_lower:
            if snapshot.display:
                lines.append(f"Displays: {snapshot.display.monitor_count} monitor(s) detected")

        if not lines:
            return ""

        context_body = "\n".join(lines)
        return f"<DESKTOP_CONTEXT>\n{context_body}\n</DESKTOP_CONTEXT>"
