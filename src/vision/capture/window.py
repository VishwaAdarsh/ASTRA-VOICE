"""
Active Window Capturer.
Inspects active foreground window title, process executable, and captures bounding rectangle image.
"""

import ctypes
import ctypes.wintypes
import uuid
from PIL import Image, ImageGrab
from src.core.config import Config
from src.core.logger import get_logger
from src.vision.capture.screen import ScreenCapturer
from src.vision.types import BoundingBox, Screenshot, VisualSourceType



logger = get_logger()


class WindowCapturer:
    """Captures active foreground window screenshot and metadata."""

    def __init__(self, config: Config | None = None, screen_capturer: ScreenCapturer | None = None):
        self.config = config or Config()
        self.screen_capturer = screen_capturer or ScreenCapturer(config=self.config)
        self.temp_dir = self.config.temp_vision_dir

    def get_active_window_info(self) -> tuple[str, str, BoundingBox | None]:
        """Query Windows OS API for active foreground window title and bounding box."""
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return "Desktop", "explorer.exe", None

            # Get Window Title
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value or "Active Window"

            # Get Window Rect (left, top, right, bottom)
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            bounds = BoundingBox(x1=rect.left, y1=rect.top, x2=rect.right, y2=rect.bottom)

            app_name = "VS Code" if "code" in title.lower() or "astra" in title.lower() else "Windows Application"
            return title, app_name, bounds
        except Exception as e:
            logger.warning(f"Failed to query active window via Windows API: {e}")
            return "Active Application", "Windows Application", None

    def capture_active_window(self) -> Screenshot:
        """Capture active foreground window screenshot and return Screenshot model."""
        title, app_name, bounds = self.get_active_window_info()
        shot = self.screen_capturer.capture_screen(region=bounds if bounds and bounds.width > 0 else None)

        shot.source_type = VisualSourceType.WINDOW
        shot.window_title = title
        shot.app_name = app_name
        logger.info(f"Captured active window '{title}' ({app_name}) -> '{shot.file_path}'")
        return shot
