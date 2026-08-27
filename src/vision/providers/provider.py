"""
Abstract Vision Provider Interface.
"""

from abc import ABC, abstractmethod
from src.vision.types import Screenshot, VisualContext


class VisionProvider(ABC):
    """Abstract interface for Vision understanding models."""

    @abstractmethod
    def analyze(self, screenshot: Screenshot, ocr_text: str = "") -> str:
        """Generate high-level visual description and analysis for a screenshot."""
        pass
