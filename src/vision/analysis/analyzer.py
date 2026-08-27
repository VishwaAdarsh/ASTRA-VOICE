import re
from src.core.config import Config
from src.core.logger import get_logger
from src.vision.analysis.ui_detection import UIDetector
from src.vision.ocr.factory import OCRProviderFactory
from src.vision.ocr.provider import OCRProvider
from src.vision.providers.factory import VisionProviderFactory
from src.vision.providers.provider import VisionProvider
from src.vision.types import Screenshot, VisualContext, VisualElement

logger = get_logger()



class VisualAnalyzer:
    """Combines OCR, Vision Provider, and UI Detector into unified visual findings."""

    def __init__(
        self,
        config: Config | None = None,
        ocr_provider: OCRProvider | None = None,
        vision_provider: VisionProvider | None = None,
        ui_detector: UIDetector | None = None,
    ):
        self.config = config or Config()
        self.ocr_provider = ocr_provider or OCRProviderFactory.create(self.config)
        self.vision_provider = vision_provider or VisionProviderFactory.create(self.config)
        self.ui_detector = ui_detector or UIDetector()

    def analyze_screenshot(self, screenshot: Screenshot) -> VisualContext:
        """Run OCR, Vision model analysis, UI element detection, and error recognition."""
        logger.info(f"VisualAnalyzer processing screenshot #{screenshot.id}")

        # 1. OCR Text Extraction
        ocr_result = self.ocr_provider.extract_text(screenshot)

        # 2. Vision Model High-Level Analysis
        description = self.vision_provider.analyze(screenshot, ocr_text=ocr_result.full_text)

        # 3. UI Element Detection
        elements = self.ui_detector.detect_elements(screenshot, ocr_result)

        # 4. Error Recognition & Extraction
        detected_errors = self._extract_errors(ocr_result.full_text)

        return VisualContext(
            screenshot=screenshot,
            ocr=ocr_result,
            elements=elements,
            description=description,
            app_name=screenshot.app_name or "Windows Application",
            window_title=screenshot.window_title or "Desktop Screen",
            detected_errors=detected_errors,
        )

    def _extract_errors(self, text: str) -> list[str]:
        """Recognize error messages, tracebacks, and dialog texts in extracted OCR text."""
        errors = []
        error_keywords = ["syntaxerror", "typeerror", "valueerror", "importerror", "permissiondenied", "failed", "exception", "error:"]

        for line in text.split("\n"):
            line_clean = line.strip()
            if any(kw in line_clean.lower() for kw in error_keywords):
                errors.append(line_clean)

        return errors
