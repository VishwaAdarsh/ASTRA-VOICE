"""
Voice Subsystem Internal Event Definitions.
Enables event-driven observation for logs, CLI state indicators, and future PySide6 GUI integration.
"""

from enum import Enum
from typing import Callable, Any


class VoiceEvent(str, Enum):
    """Internal lifecycle and transition events of the Voice Subsystem."""

    VOICE_SESSION_STARTED = "VOICE_SESSION_STARTED"
    WAKE_WORD_LISTENING_STARTED = "WAKE_WORD_LISTENING_STARTED"
    WAKE_WORD_DETECTED = "WAKE_WORD_DETECTED"
    LISTENING_STARTED = "LISTENING_STARTED"
    SPEECH_DETECTED = "SPEECH_DETECTED"
    TRANSCRIPTION_STARTED = "TRANSCRIPTION_STARTED"
    TRANSCRIPTION_COMPLETED = "TRANSCRIPTION_COMPLETED"
    COMMAND_RECEIVED = "COMMAND_RECEIVED"
    COMMAND_TIMEOUT = "COMMAND_TIMEOUT"
    PROCESSING_STARTED = "PROCESSING_STARTED"
    PROCESSING_COMPLETED = "PROCESSING_COMPLETED"
    TTS_STARTED = "TTS_STARTED"
    TTS_COMPLETED = "TTS_COMPLETED"
    VOICE_SESSION_ENDED = "VOICE_SESSION_ENDED"
    VOICE_ERROR = "VOICE_ERROR"



VoiceEventListener = Callable[[VoiceEvent, dict[str, Any]], None]
