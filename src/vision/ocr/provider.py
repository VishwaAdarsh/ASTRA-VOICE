from abc import ABC, abstractmethod
from src.vision.types import OCRResult, Screenshot



class OCRProvider(ABC):
    """Abstract interface for Optical Character Recognition engines."""

    @abstractmethod
    def extract_text(self, screenshot: Screenshot) -> OCRResult:
        """Perform OCR text extraction on target screenshot."""
        pass
