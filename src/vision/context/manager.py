from pathlib import Path
from src.core.config import Config
from src.core.logger import get_logger
from src.vision.analysis.analyzer import VisualAnalyzer
from src.vision.capture.manager import CaptureManager
from src.vision.context.builder import VisualContextBuilder
from src.vision.types import BoundingBox, OCRResult, Screenshot, VisualContext, VisualSourceType



logger = get_logger()


class VisionManager:
    """Central Vision Manager coordinating desktop capture, OCR, analysis, and cleanup."""

    def __init__(
        self,
        config: Config | None = None,
        capture_manager: CaptureManager | None = None,
        analyzer: VisualAnalyzer | None = None,
        builder: VisualContextBuilder | None = None,
    ):
        self.config = config or Config()
        self.capture_manager = capture_manager or CaptureManager(config=self.config)
        self.analyzer = analyzer or VisualAnalyzer(config=self.config)
        self.builder = builder or VisualContextBuilder()
        self._last_context: VisualContext | None = None

    def analyze_screen(self, region: BoundingBox | None = None) -> VisualContext:
        """Capture screen/region and run visual analysis."""
        shot = self.capture_manager.capture_screen(region=region)
        context = self.analyzer.analyze_screenshot(shot)
        self._last_context = context
        return context

    def analyze_active_window(self) -> VisualContext:
        """Capture active foreground window and run visual analysis."""
        shot = self.capture_manager.capture_active_window()
        context = self.analyzer.analyze_screenshot(shot)
        self._last_context = context
        return context

    def analyze_image_file(self, image_path: str | Path) -> VisualContext:
        """Parse user-provided image file."""
        path_obj = Path(image_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Image file '{image_path}' does not exist.")

        shot = Screenshot(
            id=f"file_{path_obj.stem}",
            file_path=str(path_obj),
            width=1280,
            height=720,
            source_type=VisualSourceType.FILE,
            window_title=path_obj.name,
            app_name="Image File",
        )
        context = self.analyzer.analyze_screenshot(shot)
        self._last_context = context
        return context

    def read_screen_text(self) -> OCRResult:
        """Run OCR text extraction on active screen."""
        context = self.analyze_active_window()
        return context.ocr

    def get_last_context(self) -> VisualContext | None:
        """Get most recent visual context analysis."""
        return self._last_context

    def cleanup(self) -> int:
        """Cleanup temporary screenshot images."""

        return self.capture_manager.cleanup_temp_screenshots()
