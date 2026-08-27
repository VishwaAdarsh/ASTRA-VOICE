"""
ASTRA Vision & Screen Understanding Subsystem Package (Phase 8).
"""

from src.vision.analysis.analyzer import VisualAnalyzer
from src.vision.analysis.ui_detection import UIDetector
from src.vision.capture.manager import CaptureManager
from src.vision.capture.screen import ScreenCapturer
from src.vision.capture.window import WindowCapturer
from src.vision.context.builder import VisualContextBuilder
from src.vision.context.manager import VisionManager
from src.vision.ocr.factory import OCRProviderFactory
from src.vision.ocr.provider import OCRProvider
from src.vision.providers.factory import VisionProviderFactory
from src.vision.providers.provider import VisionProvider
from src.vision.types import (
    BoundingBox,
    ElementType,
    OCRRegion,
    OCRResult,
    Screenshot,
    VisionAnalysisState,
    VisualContext,
    VisualElement,
    VisualSourceType,
)

__all__ = [
    "BoundingBox",
    "CaptureManager",
    "ElementType",
    "OCRProvider",
    "OCRProviderFactory",
    "OCRRegion",
    "OCRResult",
    "ScreenCapturer",
    "Screenshot",
    "UIDetector",
    "VisionAnalysisState",
    "VisionManager",
    "VisionProvider",
    "VisionProviderFactory",
    "VisualAnalyzer",
    "VisualContext",
    "VisualContextBuilder",
    "VisualElement",
    "VisualSourceType",
    "WindowCapturer",
]
