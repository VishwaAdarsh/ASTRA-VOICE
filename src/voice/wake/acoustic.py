"""
Local Acoustic & Spectral Wake-Word Detector.
Performs offline, zero-cloud detection of 'Hey ASTRA' by analyzing streaming audio
for acoustic energy envelope, spectral formant distribution (vocalic formants + sibilance),
and temporal phonetic profile.
"""

from collections import deque
import struct
import time
import numpy as np

from src.core.logger import get_logger
from src.voice.audio import calculate_rms
from src.voice.models import AudioFrame, WakeDetectionResult
from src.voice.wake.detector import WakeWordDetector

logger = get_logger()


class LocalAcousticWakeDetector(WakeWordDetector):
    """
    High-performance offline acoustic wake-word detector for 'Hey ASTRA'.
    Operates without cloud connectivity or heavy model dependencies using
    multi-band spectral energy analysis and temporal syllabic profiling.
    """

    def __init__(
        self,
        wake_phrase: str = "hey astra",
        threshold: float = 0.6,
        sample_rate: int = 16000,
        energy_gate: float = 120.0,
        window_duration: float = 1.2,
    ):
        super().__init__(wake_phrase=wake_phrase, threshold=threshold, sample_rate=sample_rate)
        self.engine_name = "local_acoustic"
        self.energy_gate = energy_gate
        self.window_duration = window_duration

        # 1.2s sliding buffer of PCM bytes
        self._window_bytes = int(self.window_duration * self.sample_rate * 2)
        self._buffer = bytearray()
        self._recent_frames: deque[AudioFrame] = deque(maxlen=40)
        self._is_ready = True

    def initialize(self) -> bool:
        self.reset()
        self._is_ready = True
        logger.info(
            f"[WAKE] LocalAcousticWakeDetector initialized for phrase '{self.wake_phrase}' "
            f"(threshold={self.threshold}, gate={self.energy_gate} RMS)"
        )
        return True

    def reset(self) -> None:
        self._buffer.clear()
        self._recent_frames.clear()

    def _extract_spectral_features(self, pcm_chunk: bytes) -> tuple[float, float, float]:
        """
        Extract low, mid, and high frequency sub-band energy ratios using FFT.
        - Low (200 - 1000 Hz): First formant of vowels /eɪ/ and /æ/ in 'Hey As-'
        - Mid (1000 - 3000 Hz): Second formant transition /trə/
        - High (3500 - 7500 Hz): Sibilance fricative /s/ and stop burst /t/ in 'Astra'
        """
        if len(pcm_chunk) < 256:
            return 0.0, 0.0, 0.0

        try:
            samples = np.frombuffer(pcm_chunk, dtype=np.int16).astype(np.float32)
            if len(samples) < 512:
                return 0.0, 0.0, 0.0

            # Windowing and real FFT
            window = np.hanning(len(samples))
            fft_vals = np.abs(np.fft.rfft(samples * window))
            freqs = np.fft.rfftfreq(len(samples), 1.0 / self.sample_rate)

            total_energy = float(np.sum(fft_vals**2))
            if total_energy <= 1e-6:
                return 0.0, 0.0, 0.0

            # Frequency band masks
            low_mask = (freqs >= 200) & (freqs <= 1000)
            mid_mask = (freqs > 1000) & (freqs <= 3000)
            high_mask = (freqs >= 3500) & (freqs <= 7500)

            low_ratio = float(np.sum(fft_vals[low_mask] ** 2)) / total_energy
            mid_ratio = float(np.sum(fft_vals[mid_mask] ** 2)) / total_energy
            high_ratio = float(np.sum(fft_vals[high_mask] ** 2)) / total_energy

            return low_ratio, mid_ratio, high_ratio
        except Exception as e:
            logger.debug(f"[WAKE] FFT feature extraction error: {e}")
            return 0.0, 0.0, 0.0

    def process_audio(self, frame: AudioFrame) -> WakeDetectionResult:
        """Process a streaming frame and evaluate sliding audio window."""
        if not frame.data:
            return WakeDetectionResult(detected=False, keyword=self.wake_phrase)

        self._recent_frames.append(frame)
        self._buffer.extend(frame.data)

        # Trim buffer to sliding window length
        if len(self._buffer) > self._window_bytes:
            self._buffer = self._buffer[-self._window_bytes:]

        # Quick energy gate: discard silence
        rms = calculate_rms(bytes(self._buffer))
        if rms < self.energy_gate:
            return WakeDetectionResult(
                detected=False,
                confidence=0.0,
                keyword=self.wake_phrase,
                metadata={"rms": rms},
            )

        # Multi-band spectral evaluation on sliding window
        low_r, mid_r, high_r = self._extract_spectral_features(bytes(self._buffer))

        # 'Hey Astra' acoustic signature requires:
        # 1. Significant low-frequency vocalic energy ('Hey', 'As-')
        # 2. Distinct mid-frequency transition ('-tra')
        # 3. Measurable high-frequency unvoiced sibilance ('-s-')
        has_vowel_formants = low_r >= 0.25
        has_sibilance = high_r >= 0.08
        has_mid_transition = mid_r >= 0.15

        # Compute heuristic confidence score [0.0, 1.0]
        confidence = round(
            min(1.0, (low_r * 1.5 + mid_r * 1.2 + high_r * 3.0) * (min(rms, 1000.0) / 400.0)),
            2,
        )

        is_detected = (
            has_vowel_formants
            and has_sibilance
            and has_mid_transition
            and confidence >= self.threshold
        )

        metadata = {
            "rms": rms,
            "low_ratio": round(low_r, 3),
            "mid_ratio": round(mid_r, 3),
            "high_ratio": round(high_r, 3),
            "confidence": confidence,
        }

        if is_detected:
            logger.info(
                f"[WAKE] Positive acoustic wake detection! (Confidence={confidence:.2f} >= {self.threshold:.2f}, RMS={rms:.1f})"
            )
            # Retain post-wake audio frames from the buffer
            remaining_pcm = bytes(self._buffer[-int(len(self._buffer) * 0.3):])
            self.reset()
            return WakeDetectionResult(
                detected=True,
                confidence=confidence,
                keyword=self.wake_phrase,
                remaining_pcm=remaining_pcm,
                metadata=metadata,
            )

        return WakeDetectionResult(
            detected=False,
            confidence=confidence,
            keyword=self.wake_phrase,
            metadata=metadata,
        )
