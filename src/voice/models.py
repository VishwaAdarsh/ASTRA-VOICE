"""
Voice Subsystem Models and Enums.
Defines explicit voice state transitions, configuration DTOs, and audio diagnostics.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class VoiceState(str, Enum):
    """Explicit voice interaction state machine states."""

    IDLE = "IDLE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    ERROR = "ERROR"


@dataclass
class AudioConfig:
    """Audio stream parameter configuration."""

    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    device_index: int | None = None
    listen_timeout: float = 10.0
    silence_timeout: float = 2.0
    minimum_speech_duration: float = 0.5


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
    """Single frame or buffer of PCM audio data."""

    data: bytes
    sample_rate: int = 16000
    channels: int = 1
    sample_width: int = 2  # 16-bit PCM
