"""
Analyze Screen Tool.
Captures primary desktop screen and generates visual description and UI element detection.
"""

from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.tools.base import BaseTool
from src.vision.context.manager import VisionManager

logger = get_logger()


class AnalyzeScreenTool(BaseTool):
    """Tool to capture and analyze the primary desktop screen."""

    def __init__(self, config: Config | None = None, vision_manager: VisionManager | None = None):
        self.config = config or Config()
        self.vision_manager = vision_manager or VisionManager(config=self.config)

    @property
    def name(self) -> str:
        return "analyze_screen"

    @property
    def description(self) -> str:
        return "Captures and analyzes the desktop screen, extracting OCR text and UI elements."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.SAFE

    def validate(self, parameters: dict[str, Any]) -> bool:
        return isinstance(parameters, dict)

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        try:
            context = self.vision_manager.analyze_screen()
            elements_summary = [f"[{e.element_type.value}] {e.label}" for e in context.elements[:5]]

            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=context.description,
                data={
                    "description": context.description,
                    "app_name": context.app_name,
                    "window_title": context.window_title,
                    "ocr_text": context.ocr.full_text,
                    "errors": context.detected_errors,
                    "elements": elements_summary,
                    "screenshot_path": context.screenshot.file_path,
                },
            )
        except Exception as e:
            logger.error(f"AnalyzeScreenTool failed: {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Screen analysis failed: {e}",
                error=str(e),
            )
