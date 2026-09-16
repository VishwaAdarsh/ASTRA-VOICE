"""
Local Wake Word Engine Architecture and Factory.
Enables offline, continuous, hands-free 'Hey ASTRA' voice activation without cloud API overhead.
Coordinates LocalAcousticWakeDetector, OpenWakeWordDetector, MockWakeWordDetector, and WakeWordListener.
"""

import re
from typing import TYPE_CHECKING, Any

from src.core.config import Config
from src.core.logger import get_logger
from src.voice.audio import normalize_transcript
from src.voice.models import AudioFrame, WakeDetectionResult
from src.voice.wake.acoustic import LocalAcousticWakeDetector
from src.voice.wake.detector import WakeWordDetector
from src.voice.wake.listener import WakeWordListener
from src.voice.wake.openwakeword_engine import OpenWakeWordDetector

if TYPE_CHECKING:
    from src.voice.manager import VoiceManager

logger = get_logger()


class MockWakeWordDetector(WakeWordDetector):
    """Deterministic Mock Wake Word Detector for unit testing."""

    def __init__(
        self,
        should_detect: bool = False,
        simulated_command: str | None = None,
        wake_phrase: str = "hey astra",
    ):
        super().__init__(wake_phrase=wake_phrase)
        self.engine_name = "mock"
        self.should_detect = should_detect
        self.simulated_command = simulated_command
        self._is_ready = True

    def initialize(self) -> bool:
        self._is_ready = True
        return True

    def reset(self) -> None:
        pass

    def process_audio(self, frame: AudioFrame) -> WakeDetectionResult:
        if self.should_detect:
            return WakeDetectionResult(
                detected=True,
                confidence=1.0,
                keyword=self.wake_phrase,
                extracted_command=self.simulated_command,
            )
        return WakeDetectionResult(detected=False, confidence=0.0, keyword=self.wake_phrase)

    def detect(self, pcm_data: bytes, sample_rate: int = 16000) -> tuple[bool, str | None]:
        if self.should_detect:
            return True, self.simulated_command
        return False, None


class DisabledWakeWordDetector(WakeWordDetector):
    """Null wake-word detector used when hands-free activation is disabled."""

    def __init__(self, wake_phrase: str = "hey astra"):
        super().__init__(wake_phrase=wake_phrase)
        self.engine_name = "disabled"
        self._is_ready = False

    def initialize(self) -> bool:
        self._is_ready = False
        return False

    def reset(self) -> None:
        pass

    def process_audio(self, frame: AudioFrame) -> WakeDetectionResult:
        return WakeDetectionResult(detected=False, confidence=0.0, keyword=self.wake_phrase)


class LocalWakeWordDetector(LocalAcousticWakeDetector):
    """
    Local Wake Word Detector for 'Hey ASTRA'.
    Operates offline, evaluating acoustic/spectral wake patterns with command extraction.
    """

    def __init__(
        self,
        wake_phrase: str = "hey astra",
        sensitivity: float = 0.6,
        energy_threshold: float = 120.0,
    ):
        super().__init__(
            wake_phrase=wake_phrase,
            threshold=sensitivity,
            energy_gate=energy_threshold,
        )
        self.sensitivity = sensitivity
        self.energy_threshold = energy_threshold

        # Regex pattern for 'Hey ASTRA' variations and command extraction
        self.wake_regex = re.compile(
            r"\b(?:hey|hay|hi|ok|okay)?\s*astra\b",
            re.IGNORECASE,
        )
        self.strict_wake_regex = re.compile(
            r"\b(?:hey|hay|hi)[,\s]+\s*astra\b",
            re.IGNORECASE,
        )

    def extract_command(self, raw_text: str) -> tuple[bool, str | None]:
        """
        Check if raw text contains wake phrase and extract any trailing command.
        Maintained for backwards compatibility with existing test suites.
        """
        cleaned = normalize_transcript(raw_text)
        if not cleaned:
            return False, None

        # Check for strict 'hey astra' pattern
        match = self.strict_wake_regex.search(cleaned)
        if not match:
            if "hey astra" in cleaned.lower() or "hey, astra" in cleaned.lower() or "hey astra," in cleaned.lower():
                match = True
            else:
                return False, None

        # Extract trailing command after wake phrase
        cmd = re.sub(
            r"^\s*(?:hey|hay|hi|ok|okay)?[,\s]*\s*astra[,\s]*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip()
        cmd = cmd.strip(" .,!?:;")

        logger.info(f"[WAKE] Positive detection! Transcript: '{cleaned}' -> Extracted command: '{cmd or None}'")
        return True, (cmd if cmd else None)


class WakeWordDetectorFactory:
    """Factory creating configured local wake-word detectors with fallback protection."""

    @staticmethod
    def create(config: Config | None = None, **kwargs) -> WakeWordDetector:
        cfg = config or Config()

        # Check if wake-word is globally disabled
        if not getattr(cfg, "wake_word_enabled", True):
            return DisabledWakeWordDetector(wake_phrase=getattr(cfg, "wake_word_phrase", "hey astra"))

        engine_name = getattr(cfg, "wake_word_engine", "local_acoustic").strip().lower()

        if engine_name == "mock":
            return MockWakeWordDetector(**kwargs)

        elif engine_name in ("openwakeword", "onnx"):
            try:
                model_path = getattr(cfg, "wake_word_model_path", "")
                detector = OpenWakeWordDetector(
                    wake_phrase=getattr(cfg, "wake_word_phrase", "hey astra"),
                    model_path=model_path,
                    threshold=getattr(cfg, "wake_word_sensitivity", 0.6),
                )
                detector.initialize()
                return detector
            except Exception as e:
                logger.warning(
                    f"[WAKE] openWakeWord initialization failed ({e}). "
                    "Falling back to LocalAcousticWakeDetector."
                )
                return LocalAcousticWakeDetector(
                    wake_phrase=getattr(cfg, "wake_word_phrase", "hey astra"),
                    threshold=getattr(cfg, "wake_word_sensitivity", 0.6),
                )

        else:
            # Default production engine: LocalAcousticWakeDetector
            detector = LocalAcousticWakeDetector(
                wake_phrase=getattr(cfg, "wake_word_phrase", "hey astra"),
                threshold=getattr(cfg, "wake_word_sensitivity", 0.6),
            )
            detector.initialize()
            return detector
