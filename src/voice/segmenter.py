"""
Speech Segmentation Engine.
Consumes continuous audio frames, maintains a rolling pre-roll buffer,
detects speech onset, accumulates utterance frames, enforces minimum/maximum duration limits,
and segments speech on trailing silence.
"""

from collections import deque
import time
from src.core.logger import get_logger
from src.voice.audio import pcm_duration_seconds
from src.voice.models import AudioConfig, AudioFrame, AudioSegment, VADState
from src.voice.vad import VoiceActivityDetector

logger = get_logger()


class SpeechSegmenter:
    """Segments continuous audio streams into discrete AudioSegments using VAD and temporal buffers."""

    def __init__(
        self,
        vad: VoiceActivityDetector | None = None,
        audio_config: AudioConfig | None = None,
        pre_roll_duration: float | None = None,
        post_roll_duration: float | None = None,
        silence_timeout: float | None = None,
        minimum_speech_duration: float | None = None,
        maximum_utterance_duration: float | None = None,
    ):
        if not isinstance(audio_config, AudioConfig):
            self.config = AudioConfig()
        else:
            self.config = audio_config

        self.pre_roll_duration = pre_roll_duration if pre_roll_duration is not None else getattr(self.config, "pre_roll_duration", 0.5)
        self.post_roll_duration = post_roll_duration if post_roll_duration is not None else getattr(self.config, "post_roll_duration", 0.3)
        self.silence_timeout = silence_timeout if silence_timeout is not None else getattr(self.config, "silence_timeout", 1.0)
        self.minimum_speech_duration = minimum_speech_duration if minimum_speech_duration is not None else getattr(self.config, "minimum_speech_duration", 0.3)
        self.maximum_utterance_duration = maximum_utterance_duration if maximum_utterance_duration is not None else getattr(self.config, "maximum_utterance_duration", 15.0)

        threshold = getattr(self.config, "energy_threshold", 300.0)
        if not isinstance(threshold, (int, float)):
            threshold = 300.0

        self.vad = vad or VoiceActivityDetector(
            energy_threshold=threshold,
            silence_timeout=self.silence_timeout,
            minimum_speech_duration=self.minimum_speech_duration,
        )

        # Compute pre-roll buffer size in frames based on frame duration
        frame_ms = getattr(self.config, "frame_duration_ms", 30)
        if not isinstance(frame_ms, (int, float)):
            frame_ms = 30
        frame_duration_s = max(0.01, frame_ms / 1000.0)
        self._pre_roll_capacity = max(1, int(self.pre_roll_duration / frame_duration_s))

        self._pre_roll_buffer: deque[AudioFrame] = deque(maxlen=self._pre_roll_capacity)
        self._speech_frames: list[AudioFrame] = []
        self._state = VADState.SILENCE

        self._speech_start_ts = 0.0
        self._last_speech_ts = 0.0
        self._silence_start_ts = 0.0

    @property
    def state(self) -> VADState:
        """Get current VAD segmentation state."""
        return self._state

    @property
    def is_capturing(self) -> bool:
        """Check if currently inside an active speech segment."""
        return self._state in (VADState.SPEECH_START, VADState.SPEECH_CONTINUES)

    def reset(self) -> None:
        """Reset internal segmenter buffers and temporal counters to idle silence."""
        self._pre_roll_buffer.clear()
        self._speech_frames.clear()
        self._state = VADState.SILENCE
        self._speech_start_ts = 0.0
        self._last_speech_ts = 0.0
        self._silence_start_ts = 0.0
        self.vad.reset()

    def process_frame(self, frame: AudioFrame) -> tuple[VADState, AudioSegment | None]:
        """
        Process a single incoming audio frame.
        Returns:
            (vad_state, completed_audio_segment_if_any)
        """
        is_speech = self.vad.is_speech(frame.data)
        now = frame.timestamp or time.time()

        if self._state == VADState.SILENCE:
            if is_speech:
                # Speech Start detected!
                self._state = VADState.SPEECH_START
                self._speech_start_ts = now
                self._last_speech_ts = now
                self._silence_start_ts = 0.0

                # Initialize speech buffer with pre-roll buffer contents + current frame
                self._speech_frames = list(self._pre_roll_buffer)
                self._speech_frames.append(frame)
                self._pre_roll_buffer.clear()

                logger.debug(
                    f"Speech START detected (Energy={self.vad.calculate_energy(frame.data):.1f} >= {self.vad.energy_threshold:.1f}). "
                    f"Pre-roll prepended: {len(self._speech_frames)-1} frames."
                )
                return VADState.SPEECH_START, None
            else:
                # Continuous silence: maintain rolling pre-roll buffer
                self._pre_roll_buffer.append(frame)
                return VADState.SILENCE, None

        else:
            # Currently in active speech (SPEECH_START or SPEECH_CONTINUES)
            self._speech_frames.append(frame)
            current_duration = pcm_duration_seconds(
                b"".join(f.data for f in self._speech_frames),
                sample_rate=self.config.sample_rate,
                channels=self.config.channels,
                sample_width=self.config.sample_width,
            )

            # 1. Check Maximum Utterance Duration Safety Guard
            if current_duration >= self.maximum_utterance_duration:
                logger.warning(
                    f"Maximum utterance duration ({self.maximum_utterance_duration:.1f}s) reached. "
                    "Finalizing segment to prevent unbounded capture."
                )
                segment = self._finalize_segment(current_duration)
                return VADState.SPEECH_END, segment

            # 2. Track Speech Continuation vs Silence
            if is_speech:
                self._state = VADState.SPEECH_CONTINUES
                self._last_speech_ts = now
                self._silence_start_ts = 0.0
                return VADState.SPEECH_CONTINUES, None
            else:
                # Non-speech frame during active utterance
                if self._silence_start_ts == 0.0:
                    self._silence_start_ts = now

                silence_elapsed = now - self._silence_start_ts

                # Check if trailing silence exceeded threshold
                if silence_elapsed >= self.silence_timeout:
                    # Speech segment complete!
                    net_speech_duration = current_duration - silence_elapsed

                    # Discard if below minimum speech duration (noise artifact / click)
                    if net_speech_duration < self.minimum_speech_duration:
                        logger.info(
                            f"Speech duration ({net_speech_duration:.2f}s) below minimum "
                            f"({self.minimum_speech_duration:.2f}s). Discarding as noise artifact."
                        )
                        self.reset()
                        return VADState.SILENCE, None

                    logger.debug(
                        f"Speech END detected after {silence_elapsed:.2f}s silence. "
                        f"Total segment duration: {current_duration:.2f}s."
                    )
                    segment = self._finalize_segment(current_duration)
                    return VADState.SPEECH_END, segment
                else:
                    self._state = VADState.SPEECH_CONTINUES
                    return VADState.SPEECH_CONTINUES, None

    def _finalize_segment(self, duration_s: float) -> AudioSegment:
        """Package accumulated speech frames into a finalized AudioSegment and reset state."""
        raw_pcm = b"".join(f.data for f in self._speech_frames)
        segment = AudioSegment(
            pcm_data=raw_pcm,
            sample_rate=self.config.sample_rate,
            channels=self.config.channels,
            sample_width=self.config.sample_width,
            duration_s=duration_s,
            speech_start_ts=self._speech_start_ts,
            speech_end_ts=self._last_speech_ts or time.time(),
        )
        self.reset()
        return segment
