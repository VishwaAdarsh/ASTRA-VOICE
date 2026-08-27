"""
Capture Manager Subsystem.
Orchestrates screen capture tasks and manages temporary screenshot cleanup.
"""

from pathlib import Path
from src.core.config import Config
from src.core.logger import get_logger
from src.vision.capture.screen import ScreenCapturer
from src.vision.capture.window import WindowCapturer
from src.vision.types import BoundingBox, Screenshot


logger = get_logger()


class CaptureManager:
    """Manages screenshot capture tasks and temporary directory lifecycle."""

    def __init__(
        self,
        config: Config | None = None,
        screen_capturer: ScreenCapturer | None = None,
        window_capturer: WindowCapturer | None = None,
    ):
        self.config = config or Config()
        self.screen_capturer = screen_capturer or ScreenCapturer(config=self.config)
        self.window_capturer = window_capturer or WindowCapturer(config=self.config, screen_capturer=self.screen_capturer)

    def capture_screen(self, region: BoundingBox | None = None) -> Screenshot:
        """Capture desktop screen or bounding region."""
        return self.screen_capturer.capture_screen(region=region)

    def capture_active_window(self) -> Screenshot:
        """Capture active foreground window."""
        return self.window_capturer.capture_active_window()

    def cleanup_temp_screenshots(self) -> int:
        """Delete temporary screenshot files from temp_vision_dir."""
        temp_dir = self.config.temp_vision_dir
        count = 0
        if temp_dir.exists():
            for shot_file in temp_dir.glob("*.png"):
                try:
                    shot_file.unlink()
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete temp screenshot '{shot_file}': {e}")
        if count > 0:
            logger.info(f"CaptureManager: Cleaned up {count} temporary screenshots.")
        return count
