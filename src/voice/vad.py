"""
Voice Activity Detection (VAD) System.
Analyzes audio buffers for speech detection and trailing silence timeouts.
"""

from src.core.logger import get_logger
from src.voice.audio import calculate_rms

logger = get_logger()


class VoiceActivityDetector:
    """Detects voice activity and trailing silence from audio PCM data."""

    def __init__(
        self,
        energy_threshold: float = 300.0,
        silence_timeout: float = 2.0,
        minimum_speech_duration: float = 0.5,
    ):
        self.energy_threshold = energy_threshold
        self.silence_timeout = silence_timeout
        self.minimum_speech_duration = minimum_speech_duration

    def is_speech(self, pcm_chunk: bytes) -> bool:
        """Check if an audio chunk contains speech energy above threshold."""
        rms = calculate_rms(pcm_chunk)
        return rms >= self.energy_threshold

    def filter_silence(self, pcm_data: bytes) -> bool:
        """Evaluate if the recorded buffer contains meaningful speech."""
        rms = calculate_rms(pcm_data)
        logger.info(f"VAD energy evaluation: RMS = {rms:.1f} (Threshold = {self.energy_threshold:.1f})")
        return rms >= self.energy_threshold
