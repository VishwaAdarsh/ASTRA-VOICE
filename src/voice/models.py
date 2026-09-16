"""
Voice Subsystem Models, Enums, and Data Transfer Objects.
Defines explicit voice state transitions, VAD signals, configuration containers,
segmented audio buffers, transcription results, and latency telemetry.
"""

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any


class VoiceState(str, Enum):
    """Explicit voice interaction state machine states."""

    IDLE = "IDLE"
    WAKE_WORD_LISTENING = "WAKE_WORD_LISTENING"
    LISTENING = "LISTENING"
    SPEECH_DETECTED = "SPEECH_DETECTED"
    CAPTURING = "CAPTURING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    INTERRUPTED = "INTERRUPTED"
    ERROR = "ERROR"


class VADState(str, Enum):
    """Voice Activity Detection signal states."""

    SILENCE = "SILENCE"
    SPEECH_START = "SPEECH_START"
    SPEECH_CONTINUES = "SPEECH_CONTINUES"
    SPEECH_END = "SPEECH_END"


@dataclass
class AudioConfig:
    """Audio stream parameter and speech segmentation configuration."""

    sample_rate: int = 16000
    channels: int = 1
    frame_duration_ms: int = 30
    chunk_size: int = 480  # 16000 * 0.03 = 480 samples
    sample_width: int = 2  # 16-bit PCM (2 bytes per sample)
    audio_format: str = "int16"
    device_index: int | None = None
    input_device: str | int | None = None
    output_device: str | int | None = None
    listen_timeout: float = 10.0
    silence_timeout: float = 1.0
    minimum_speech_duration: float = 0.3
    maximum_utterance_duration: float = 15.0
    pre_roll_duration: float = 0.5
    post_roll_duration: float = 0.3
    energy_threshold: float = 300.0


@dataclass
class VoiceConfig:
    """Voice subsystem master configuration."""

    enabled: bool = True
    stt_provider: str = "speech_recognition"
    tts_provider: str = "pyttsx3"
    microphone_device: str = "default"
    tts_rate: int = 175
    tts_volume: float = 1.0
    voice_language: str = "en-US"
    api_key: str = ""
    audio: AudioConfig = field(default_factory=AudioConfig)


@dataclass
class AudioDiagnostics:
    """Diagnostic readout of current audio input device."""

    device_name: str
    sample_rate: int
    channels: int
    status: str
    is_available: bool = True


@dataclass
class AudioFrame:
    """Single frame or small chunk of PCM audio data."""

    data: bytes
    sample_rate: int = 16000
    channels: int = 1
    sample_width: int = 2  # 16-bit PCM
    timestamp: float = field(default_factory=time.time)


@dataclass
class AudioSegment:
    """Segment of contiguous speech audio bounded by VAD with pre/post-roll."""

    pcm_data: bytes
    sample_rate: int = 16000
    channels: int = 1
    sample_width: int = 2
    duration_s: float = 0.0
    speech_start_ts: float = 0.0
    speech_end_ts: float = 0.0


@dataclass
class STTResult:
    """Speech-to-Text transcription output with optional metadata."""

    transcript: str
    confidence: float | None = None
    language: str | None = "en-US"
    duration_s: float = 0.0
    provider_name: str = ""

    def __str__(self) -> str:
        return self.transcript


@dataclass
class VoiceMetrics:
    """Voice pipeline latency and timing telemetry."""

    capture_start_ts: float = 0.0
    speech_detected_ts: float = 0.0
    speech_end_ts: float = 0.0
    stt_start_ts: float = 0.0
    stt_end_ts: float = 0.0
    agent_start_ts: float = 0.0
    agent_end_ts: float = 0.0
    tts_start_ts: float = 0.0
    tts_end_ts: float = 0.0
    total_duration_s: float = 0.0

    @property
    def speech_to_stt_ms(self) -> float:
        """Latency from speech completion to STT initiation."""
        if self.speech_end_ts > 0 and self.stt_start_ts >= self.speech_end_ts:
            return round((self.stt_start_ts - self.speech_end_ts) * 1000.0, 1)
        return 0.0

    @property
    def stt_latency_ms(self) -> float:
        """Duration spent in Speech-to-Text transcription."""
        if self.stt_end_ts >= self.stt_start_ts > 0:
            return round((self.stt_end_ts - self.stt_start_ts) * 1000.0, 1)
        return 0.0

    @property
    def agent_latency_ms(self) -> float:
        """Duration spent in Agent cognitive reasoning and tool execution."""
        if self.agent_end_ts >= self.agent_start_ts > 0:
            return round((self.agent_end_ts - self.agent_start_ts) * 1000.0, 1)
        return 0.0

    @property
    def tts_startup_latency_ms(self) -> float:
        """Latency from Agent response completion to first TTS output audio."""
        if self.tts_start_ts >= self.agent_end_ts > 0:
            return round((self.tts_start_ts - self.agent_end_ts) * 1000.0, 1)
        return 0.0

    @property
    def total_turn_ms(self) -> float:
        """Total turn turnaround time."""
        if self.total_duration_s > 0:
            return round(self.total_duration_s * 1000.0, 1)
        if self.tts_end_ts >= self.capture_start_ts > 0:
            return round((self.tts_end_ts - self.capture_start_ts) * 1000.0, 1)
        return 0.0
