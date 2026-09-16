"""
Voice Activity Detection (VAD) Engine.
Analyzes audio frames for speech energy, adaptive noise floor tracking, and voice activity discrimination.
The VAD layer remains completely decoupled from Agent, LLM, or UI subsystems.
"""

from src.core.logger import get_logger
from src.voice.audio import calculate_rms
from src.voice.models import VADState

logger = get_logger()


class VoiceActivityDetector:
    """Evaluates audio frames to detect human voice activity using energy and noise-floor modeling."""

    def __init__(
        self,
        energy_threshold: float = 300.0,
        silence_timeout: float = 1.0,
        minimum_speech_duration: float = 0.3,
        adaptive_threshold: bool = True,
    ):
        self.base_threshold = energy_threshold
        self.energy_threshold = energy_threshold
        self.silence_timeout = silence_timeout
        self.minimum_speech_duration = minimum_speech_duration
        self.adaptive_threshold = adaptive_threshold

        # Adaptive noise floor tracking
        self.noise_floor = 50.0
        self._alpha = 0.05  # Smoothing factor for background noise floor

    def reset(self) -> None:
        """Reset adaptive noise floor and thresholds to baseline."""
        self.energy_threshold = self.base_threshold
        self.noise_floor = 50.0

    def calculate_energy(self, pcm_chunk: bytes) -> float:
        """Compute the RMS energy level for an audio chunk."""
        return calculate_rms(pcm_chunk)

    def is_speech(self, pcm_chunk: bytes) -> bool:
        """Check if an audio chunk contains speech energy above current threshold."""
        if not pcm_chunk:
            return False

        rms = self.calculate_energy(pcm_chunk)

        if self.adaptive_threshold:
            # If current energy is low, adaptively update noise floor
            if rms < self.energy_threshold * 0.7:
                self.noise_floor = (1.0 - self._alpha) * self.noise_floor + self._alpha * rms
                # Ensure threshold stays at least base_threshold or noise_floor + margin
                self.energy_threshold = max(self.base_threshold, self.noise_floor * 2.5)

        return rms >= self.energy_threshold

    def filter_silence(self, pcm_data: bytes) -> bool:
        """Evaluate if an entire audio buffer contains meaningful speech above threshold."""
        rms = self.calculate_energy(pcm_data)
        logger.debug(f"VAD energy evaluation: RMS = {rms:.1f} (Threshold = {self.energy_threshold:.1f})")
        return rms >= self.energy_threshold
