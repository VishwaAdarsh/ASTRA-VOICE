"""
Vision Subsystem Types, Enums, and Dataclasses.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ElementType(str, Enum):
    """Types of detected UI elements."""

    BUTTON = "BUTTON"
    TEXT = "TEXT"
    INPUT = "INPUT"
    CHECKBOX = "CHECKBOX"
    RADIO = "RADIO"
    IMAGE = "IMAGE"
    ICON = "ICON"
    MENU = "MENU"
    WINDOW = "WINDOW"
    TAB = "TAB"
    TABLE = "TABLE"
    LINK = "LINK"
    UNKNOWN = "UNKNOWN"


class VisualSourceType(str, Enum):
    """Source origin of visual input."""

    SCREEN = "SCREEN"
    WINDOW = "WINDOW"
    REGION = "REGION"
    FILE = "FILE"


class VisionAnalysisState(str, Enum):
    """State machine status of visual analysis task."""

    CAPTURING = "CAPTURING"
    PROCESSING = "PROCESSING"
    OCR = "OCR"
    ANALYZING = "ANALYZING"
    BUILDING_CONTEXT = "BUILDING_CONTEXT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class BoundingBox:
    """Bounding box coordinates (x1, y1, x2, y2)."""

    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return max(0, self.x2 - self.x1)

    @property
    def height(self) -> int:
        return max(0, self.y2 - self.y1)


@dataclass
class VisualElement:
    """Detected UI element record."""

    id: int
    element_type: ElementType
    label: str
    bounds: BoundingBox
    confidence: float = 1.0
    text: str = ""
    state: str = "VISIBLE"  # VISIBLE, ACTIVE, DISABLED


@dataclass
class OCRRegion:
    """Extracted text bounding region from OCR."""

    text: str
    bounds: BoundingBox
    confidence: float = 1.0


@dataclass
class OCRResult:
    """Combined OCR text extraction result."""

    full_text: str
    regions: list[OCRRegion] = field(default_factory=list)
    confidence: float = 1.0
    language: str = "en"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Screenshot:
    """Captured screenshot container."""

    id: str
    file_path: str
    width: int
    height: int
    source_type: VisualSourceType
    window_title: str | None = None
    app_name: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class VisualContext:
    """Structured visual understanding container passed to LLM Brain."""

    screenshot: Screenshot
    ocr: OCRResult
    elements: list[VisualElement] = field(default_factory=list)
    description: str = ""
    app_name: str = "Unknown"
    window_title: str = "Unknown"
    detected_errors: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
