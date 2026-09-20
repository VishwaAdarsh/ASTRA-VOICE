"""
Desktop Context Data Models and Value Objects.
Defines structured, typed containers for desktop context snapshots including active window,
application identity, multi-monitor display, file/directory inference, clipboard status,
focused UI elements, and request-driven screen capture metadata.
"""

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any


class ConfidenceLevel(str, Enum):
    """Confidence level for context inference."""

    EXACT = "EXACT"          # Direct OS API measurement (e.g. HWND, window title, PID)
    INFERRED = "INFERRED"    # Inferred from title or patterns (e.g. file name from VS Code title)
    UNKNOWN = "UNKNOWN"      # Unverified or absent information


@dataclass
class WindowBounds:
    """Screen coordinates bounding rectangle."""

    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0

    @property
    def width(self) -> int:
        return max(0, self.right - self.left)

    @property
    def height(self) -> int:
        return max(0, self.bottom - self.top)

    def to_dict(self) -> dict[str, int]:
        return {
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class WindowInfo:
    """Information regarding a desktop window."""

    hwnd: int
    title: str
    bounds: WindowBounds | None = None
    is_minimized: bool = False
    is_maximized: bool = False
    source: str = "windows_user32"

    def to_dict(self) -> dict[str, Any]:
        return {
            "hwnd": self.hwnd,
            "title": self.title,
            "bounds": self.bounds.to_dict() if self.bounds else None,
            "is_minimized": self.is_minimized,
            "is_maximized": self.is_maximized,
            "source": self.source,
        }


@dataclass
class ApplicationInfo:
    """Normalized application identity."""

    app_id: str = "unknown"
    name: str = "Unknown Application"
    executable: str = ""
    process_id: int | None = None
    is_known: bool = False
    source: str = "windows_process"

    def to_dict(self) -> dict[str, Any]:
        return {
            "app_id": self.app_id,
            "name": self.name,
            "executable": self.executable,
            "process_id": self.process_id,
            "is_known": self.is_known,
            "source": self.source,
        }


@dataclass
class DisplayInfo:
    """Display environment and monitor configuration."""

    monitor_count: int = 1
    active_display_bounds: WindowBounds | None = None
    primary_display_bounds: WindowBounds | None = None
    is_primary: bool = True
    source: str = "windows_display"

    def to_dict(self) -> dict[str, Any]:
        return {
            "monitor_count": self.monitor_count,
            "active_display_bounds": self.active_display_bounds.to_dict() if self.active_display_bounds else None,
            "primary_display_bounds": self.primary_display_bounds.to_dict() if self.primary_display_bounds else None,
            "is_primary": self.is_primary,
            "source": self.source,
        }


@dataclass
class FileInfo:
    """Inferred or identified active document or file."""

    name: str
    path: str | None = None  # None when path is not provably known; never fabricated
    confidence: ConfidenceLevel = ConfidenceLevel.INFERRED
    source: str = "window_title"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "confidence": self.confidence.value,
            "source": self.source,
        }


@dataclass
class DirectoryInfo:
    """Inferred or identified current working directory or Explorer location."""

    name: str
    path: str | None = None  # None when exact path cannot be verified
    confidence: ConfidenceLevel = ConfidenceLevel.INFERRED
    source: str = "explorer_window"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "confidence": self.confidence.value,
            "source": self.source,
        }


@dataclass
class ClipboardInfo:
    """Read-only clipboard metadata and privacy-gated content."""

    available: bool = False
    content_type: str = "none"  # 'text', 'file_paths', 'image', 'none'
    text_preview: str | None = None  # Populated ONLY on explicit request
    is_redacted: bool = False
    source: str = "windows_clipboard"

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "content_type": self.content_type,
            "text_preview": self.text_preview,
            "is_redacted": self.is_redacted,
            "source": self.source,
        }


@dataclass
class UIElementInfo:
    """Focused accessibility UI control element."""

    role: str = "unknown"
    name: str = ""
    value: str = ""
    source: str = "windows_accessibility"

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "name": self.name,
            "value": self.value,
            "source": self.source,
        }


@dataclass
class ScreenInfo:
    """Screen capture metadata for request-driven visual context."""

    available: bool = True
    captured: bool = False
    screenshot_path: str | None = None
    description: str | None = None
    source: str = "vision_screen"

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "captured": self.captured,
            "screenshot_path": self.screenshot_path,
            "description": self.description,
            "source": self.source,
        }


@dataclass
class DesktopContextSnapshot:
    """Coherent, immutable snapshot of the desktop environment at a point in time."""

    timestamp: float = field(default_factory=time.time)
    active_window: WindowInfo | None = None
    active_application: ApplicationInfo | None = None
    display: DisplayInfo | None = None
    active_file: FileInfo | None = None
    current_directory: DirectoryInfo | None = None
    clipboard: ClipboardInfo | None = None
    focused_element: UIElementInfo | None = None
    screen: ScreenInfo | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def age_seconds(self) -> float:
        """Elapsed time since snapshot was captured."""
        return max(0.0, time.time() - self.timestamp)

    def is_stale(self, max_age_seconds: float = 2.0) -> bool:
        """Check whether snapshot has exceeded freshness threshold."""
        return self.age_seconds > max_age_seconds

    def to_dict(self) -> dict[str, Any]:
        """Serialize snapshot to JSON-safe dictionary."""
        return {
            "timestamp": self.timestamp,
            "age_seconds": round(self.age_seconds, 3),
            "active_window": self.active_window.to_dict() if self.active_window else None,
            "active_application": self.active_application.to_dict() if self.active_application else None,
            "display": self.display.to_dict() if self.display else None,
            "active_file": self.active_file.to_dict() if self.active_file else None,
            "current_directory": self.current_directory.to_dict() if self.current_directory else None,
            "clipboard": self.clipboard.to_dict() if self.clipboard else None,
            "focused_element": self.focused_element.to_dict() if self.focused_element else None,
            "screen": self.screen.to_dict() if self.screen else None,
            "metadata": self.metadata,
        }
