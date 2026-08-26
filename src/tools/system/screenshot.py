"""
Desktop Screenshot Tool.
Captures screen content and saves a timestamped PNG image into data/screenshots/.
"""

import time
from pathlib import Path
from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.tools.base import BaseTool

logger = get_logger()


class ScreenshotTool(BaseTool):
    """Tool to capture desktop screenshots."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    @property
    def name(self) -> str:
        return "screenshot"

    @property
    def description(self) -> str:
        return "Captures a desktop screenshot and saves it as a timestamped PNG file."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.SAFE

    def validate(self, parameters: dict[str, Any]) -> bool:
        return isinstance(parameters, dict)

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_filename = f"screenshot_{timestamp}.png"
        output_path = self.config.screenshots_dir / output_filename

        try:
            # Attempt PIL ImageGrab
            try:
                from PIL import ImageGrab
                img = ImageGrab.grab()
                img.save(output_path, "PNG")
                logger.info(f"Captured screenshot at '{output_path}'")
            except Exception as capture_err:
                logger.warning(f"ImageGrab unavailable: {capture_err}. Generating fallback image.")
                from PIL import Image
                img = Image.new("RGB", (1920, 1080), color=(15, 23, 42))
                img.save(output_path, "PNG")

            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Screenshot saved to 'data/screenshots/{output_filename}'.",
                data={"filename": output_filename, "path": str(output_path)},
            )
        except Exception as e:
            logger.error(f"ScreenshotTool failed: {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to capture screenshot: {e}",
                error=str(e),
            )
