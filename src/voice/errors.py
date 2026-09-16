"""
ASTRA Voice Subsystem Domain Exceptions.
Structured exception hierarchy for audio hardware, VAD, STT, and TTS engines.
"""

from src.core.exceptions import AstraError


class VoiceError(AstraError):
    """Base exception for all voice subsystem failures."""

    pass


class MicrophoneUnavailableError(VoiceError):
    """Raised when no valid audio input hardware is detected or accessible."""

    pass


class AudioDeviceError(VoiceError):
    """Raised when an audio input/output device operation fails or format is unsupported."""

    pass


class VADError(VoiceError):
    """Raised when voice activity detection fails or encounters invalid audio buffers."""

    pass


class STTError(VoiceError):
    """Base exception for Speech-to-Text transcription failures."""

    pass


class STTTimeoutError(STTError):
    """Raised when STT transcription exceeds configured timeout limits."""

    pass


class EmptyTranscriptError(VoiceError):
    """Raised or flagged when audio capture yields empty or noise-only transcript."""

    pass


class TTSError(VoiceError):
    """Base exception for Text-to-Speech synthesis failures."""

    pass


class TTSTimeoutError(TTSError):
    """Raised when TTS synthesis or playback times out."""

    pass


class VoiceConfigurationError(VoiceError):
    """Raised when voice subsystem parameters or provider specifications are invalid."""

    pass


class WakeWordError(VoiceError):
    """Base exception for wake-word detection subsystem errors."""

    pass


class WakeModelMissingError(WakeWordError):
    """Raised when the specified wake-word model file cannot be located."""

    pass


class WakeModelInvalidError(WakeWordError):
    """Raised when the wake-word model format or structure is invalid or corrupt."""

    pass


class WakeDetectorInitError(WakeWordError):
    """Raised when initializing the local wake-word detector fails."""

    pass

