"""
Abstract Wake-Word Detector Interface and Base Classes.
Defines the contract for production local wake-word engines without cloud dependencies.
"""

from abc import ABC, abstractmethod
from typing import Any
from src.voice.models import AudioFrame, WakeDetectionResult


class WakeWordDetector(ABC):
    """Abstract interface for local streaming wake-word detectors."""

    def __init__(
        self,
        wake_phrase: str = "hey astra",
        threshold: float = 0.6,
        sample_rate: int = 16000,
    ):
        self.wake_phrase = wake_phrase.strip().lower()
        self.threshold = threshold
        self.sample_rate = sample_rate
        self.engine_name = "base"
        self._is_ready = False

    @abstractmethod
    def initialize(self) -> bool:
        """Initialize local acoustic models, ONNX sessions, or DSP structures."""
        pass

    @abstractmethod
    def process_audio(self, frame: AudioFrame) -> WakeDetectionResult:
        """
        Process a single streaming AudioFrame.
        Returns:
            WakeDetectionResult containing detection state, confidence, and metadata.
        """
        pass

    def detect(self, pcm_data: bytes, sample_rate: int = 16000) -> tuple[bool, str | None]:
        """
        Legacy/compat convenience method: Process raw PCM bytes and return (detected, extracted_command).
        """
        frame = AudioFrame(data=pcm_data, sample_rate=sample_rate)
        res = self.process_audio(frame)
        return res.detected, res.extracted_command

    @abstractmethod
    def reset(self) -> None:
        """Reset internal streaming buffers, hidden states, or temporal sliding windows."""
        pass

    def start(self) -> None:
        """Optional hook when detection starts."""
        self.reset()

    def stop(self) -> None:
        """Optional hook when detection stops."""
        pass

    def close(self) -> None:
        """Release underlying ONNX runtime sessions or audio memory."""
        self.stop()
        self._is_ready = False

    def is_ready(self) -> bool:
        """Check if detector is initialized and ready for streaming inference."""
        return self._is_ready
