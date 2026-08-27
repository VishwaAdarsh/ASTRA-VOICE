"""
Analyze Image Tool.
Parses and analyzes a target image file from the filesystem.
"""

from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.tools.base import BaseTool
from src.vision.context.manager import VisionManager

logger = get_logger()


class AnalyzeImageTool(BaseTool):
    """Tool to analyze user-provided image files."""

    def __init__(self, config: Config | None = None, vision_manager: VisionManager | None = None):
        self.config = config or Config()
        self.vision_manager = vision_manager or VisionManager(config=self.config)

    @property
    def name(self) -> str:
        return "analyze_image"

    @property
    def description(self) -> str:
        return "Analyzes a target image file from the filesystem."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.SAFE

    def validate(self, parameters: dict[str, Any]) -> bool:
        return "image_path" in parameters and isinstance(parameters["image_path"], str)

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        image_path = str(parameters["image_path"]).strip()

        try:
            context = self.vision_manager.analyze_image_file(image_path)
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=context.description,
                data={
                    "description": context.description,
                    "ocr_text": context.ocr.full_text,
                    "errors": context.detected_errors,
                    "image_path": image_path,
                },
            )
        except Exception as e:
            logger.error(f"AnalyzeImageTool failed for '{image_path}': {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Image analysis failed: {e}",
                error=str(e),
            )
