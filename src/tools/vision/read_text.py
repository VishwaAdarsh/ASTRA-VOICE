"""
Read Screen Text Tool.
Performs OCR text extraction on the screen or active window.
"""

from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.tools.base import BaseTool
from src.vision.context.manager import VisionManager

logger = get_logger()


class ReadScreenTextTool(BaseTool):
    """Tool to read visible screen text via OCR."""

    def __init__(self, config: Config | None = None, vision_manager: VisionManager | None = None):
        self.config = config or Config()
        self.vision_manager = vision_manager or VisionManager(config=self.config)

    @property
    def name(self) -> str:
        return "read_screen_text"

    @property
    def description(self) -> str:
        return "Reads visible on-screen text using OCR."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.SAFE

    def validate(self, parameters: dict[str, Any]) -> bool:
        return isinstance(parameters, dict)

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        try:
            ocr_result = self.vision_manager.read_screen_text()
            msg = f"Extracted {len(ocr_result.full_text)} characters of text from screen."
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=msg,
                data={
                    "text": ocr_result.full_text,
                    "confidence": ocr_result.confidence,
                    "language": ocr_result.language,
                },
            )
        except Exception as e:
            logger.error(f"ReadScreenTextTool failed: {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"OCR text extraction failed: {e}",
                error=str(e),
            )
