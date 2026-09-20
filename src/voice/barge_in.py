"""
Voice Barge-In & Interruption Subsystem.
Enables real-time interruption of TTS speech playback when user speech is detected
via continuous microphone capture and energy-based VAD with false-positive protection.
"""

from collections import deque
import threading
import time
from typing import TYPE_CHECKING, Callable

from src.core.config import Config
from src.core.logger import get_logger
from src.voice.audio import audio_rms
from src.voice.events import VoiceEvent
from src.voice.models import AudioFrame, BargeInConfig, VoiceMetrics, VoiceState

if TYPE_CHECKING:
    from src.voice.manager import VoiceManager
    from src.voice.session import VoiceSession

logger = get_logger()


class BargeInDetector:
    """
    Detects user speech during active Text-To-Speech (TTS) playback and triggers immediate interruption.
    Uses continuous microphone audio frames, energy RMS thresholding, sustained duration gating,
    and speaker bleed suppression.
    """

    def __init__(
        self,
        config: Config | None = None,
        on_interrupted: Callable[..., None] | None = None,
    ):
        self.config = config or Config()
        self.enabled = getattr(self.config, "barge_in_enabled", True)
        self.energy_threshold = getattr(self.config, "barge_in_energy_threshold", 650.0)
        self.min_speech_duration = getattr(self.config, "barge_in_min_speech_duration", 0.25)
        self.cooldown_seconds = getattr(self.config, "barge_in_cooldown", 1.5)
        self.grace_period_seconds = getattr(self.config, "barge_in_grace_period", 0.2)

        self.on_interrupted = on_interrupted
        self._speech_buffer: list[AudioFrame] = []
        self._pre_roll: deque[AudioFrame] = deque(maxlen=15)  # ~450ms history
        self._consecutive_speech_frames = 0
        self._speech_start_ts: float | None = None
        self._cooldown_until: float = 0.0
        self._is_monitoring = False
        self._lock = threading.RLock()

    def reset(self) -> None:
        """Reset internal frame counters and buffers."""
        with self._lock:
            self._speech_buffer.clear()
            self._pre_roll.clear()
            self._consecutive_speech_frames = 0
            self._speech_start_ts = None

    def start_monitoring(self) -> None:
        """Arm the barge-in detector for an active speech turn."""
        with self._lock:
            self.reset()
            self._is_monitoring = True

    def stop_monitoring(self) -> None:
        """Disarm the barge-in detector."""
        with self._lock:
            self._is_monitoring = False
            self.reset()

    def is_monitoring(self) -> bool:
        """Check if barge-in detection is currently armed."""
        return self._is_monitoring

    def check_frame(
        self,
        frame: AudioFrame,
        tts_start_ts: float,
    ) -> tuple[bool, list[AudioFrame]]:
        """
        Evaluate a single audio frame captured during TTS playback.
        Returns (is_barge_in_confirmed, buffered_speech_frames).
        """
        if not self.enabled or not self._is_monitoring:
            return False, []

        now = time.time()

        # 1. Cooldown check
        if now < self._cooldown_until:
            return False, []

        # 2. Grace period check (suppress first ~200ms of TTS output ramp-up)
        if (now - tts_start_ts) < self.grace_period_seconds:
            with self._lock:
                self._pre_roll.append(frame)
            return False, []

        # 3. Calculate energy RMS
        rms = audio_rms(frame.data)

        with self._lock:
            if rms >= self.energy_threshold:
                if self._consecutive_speech_frames == 0:
                    self._speech_start_ts = now
                self._consecutive_speech_frames += 1
                self._speech_buffer.append(frame)

                # Calculate sustained duration
                frame_duration = len(frame.data) / (frame.sample_rate * frame.sample_width)
                accumulated_duration = self._consecutive_speech_frames * frame_duration

                if accumulated_duration >= self.min_speech_duration:
                    logger.info(
                        f"[BARGE-IN] User speech confirmed! (RMS: {rms:.1f} >= {self.energy_threshold:.1f}, "
                        f"Duration: {accumulated_duration:.2f}s >= {self.min_speech_duration:.2f}s)"
                    )
                    # Gather pre-roll + speech buffer to preserve initial phonemes
                    handoff_frames = list(self._pre_roll) + list(self._speech_buffer)
                    self._cooldown_until = now + self.cooldown_seconds
                    self._is_monitoring = False
                    self._speech_buffer.clear()
                    self._consecutive_speech_frames = 0
                    return True, handoff_frames
            else:
                # Signal dropped below threshold
                if self._consecutive_speech_frames > 0:
                    # Noise spike or click that didn't reach min duration
                    self._consecutive_speech_frames = 0
                    self._speech_buffer.clear()
                    self._speech_start_ts = None
                self._pre_roll.append(frame)

        return False, []


class BargeInCoordinator:
    """
    Coordinates BargeInDetector monitoring during VoiceSession speaking lifecycle.
    Manages concurrent microphone frame consumption while TTS is actively playing.
    """

    def __init__(
        self,
        voice_session: "VoiceSession",
        config: Config | None = None,
    ):
        self.session = voice_session
        self.config = config or getattr(voice_session, "config", Config())
        self.detector = BargeInDetector(config=self.config)
        self._interrupted_event = threading.Event()
        self._buffered_frames: list[AudioFrame] = []

    def monitor_while_speaking(
        self,
        text: str,
        tts_start_ts: float,
        metrics: VoiceMetrics,
        timeout: float = 30.0,
    ) -> bool:
        """
        Monitor continuous microphone frames for user speech while TTS plays.
        If user interrupts:
          1. Stops TTS immediately.
          2. Records latency metrics.
          3. Slices and stores buffered speech frames for speech segmentation.
          4. Returns True (interrupted).
        If speech finishes naturally without interruption:
          Returns False.
        """
        if not getattr(self.config, "barge_in_enabled", True):
            # If barge-in disabled, wait for TTS to complete normally
            return False

        self.detector.start_monitoring()
        self._interrupted_event.clear()
        self._buffered_frames = []

        start_time = time.time()
        interrupted = False

        try:
            while self.session.tts.is_speaking():
                if (time.time() - start_time) > timeout:
                    logger.warning("[BARGE-IN] Monitoring timed out while waiting for TTS completion.")
                    break

                # Read microphone frame from continuous stream
                frame = self.session.mic.read_frame(timeout=0.05)
                if frame is None:
                    continue

                is_barge_in, frames = self.detector.check_frame(frame, tts_start_ts=tts_start_ts)
                if is_barge_in:
                    interrupted = True
                    barge_in_ts = time.time()
                    metrics.barge_in_detected_ts = barge_in_ts
                    metrics.tts_stop_requested_ts = barge_in_ts

                    # 1. Halt TTS immediately
                    logger.info("[BARGE-IN] Halting active TTS playback...")
                    self.session.tts.stop()
                    metrics.tts_stopped_ts = time.time()

                    # 2. Preserve buffered frames
                    self._buffered_frames = frames

                    # 3. Transition state to INTERRUPTING then INTERRUPTED
                    self.session._set_state(VoiceState.BARGE_IN_DETECTED)
                    self.session.emit_event(
                        VoiceEvent.BARGE_IN_DETECTED,
                        {
                            "barge_in_latency_ms": metrics.barge_in_detection_latency_ms,
                            "timestamp": barge_in_ts,
                        },
                    )
                    self.session._set_state(VoiceState.INTERRUPTING)
                    self.session.emit_event(VoiceEvent.TTS_STOP_REQUESTED)
                    self.session._set_state(VoiceState.INTERRUPTED)
                    self.session.emit_event(
                        VoiceEvent.VOICE_INTERRUPTED,
                        {
                            "tts_stop_latency_ms": metrics.tts_stop_latency_ms,
                            "total_interruption_latency_ms": metrics.total_interruption_latency_ms,
                        },
                    )
                    break

        finally:
            self.detector.stop_monitoring()

        return interrupted

    @property
    def buffered_speech_frames(self) -> list[AudioFrame]:
        """Frames captured during the barge-in confirmation window."""
        return self._buffered_frames
