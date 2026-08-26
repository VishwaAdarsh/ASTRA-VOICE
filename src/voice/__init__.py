"""
ASTRA Voice Subsystem Package (Phase 2).
Provides microphone capture, VAD, STT, TTS, voice state machine, and session management.
"""

from src.voice.audio import calculate_rms, convert_to_wav, normalize_transcript
from src.voice.events import VoiceEvent, VoiceEventListener
from src.voice.manager import VoiceManager
from src.voice.microphone import MicrophoneManager, MicrophoneUnavailableError
from src.voice.models import AudioConfig, AudioDiagnostics, AudioFrame, VoiceConfig, VoiceState
from src.voice.session import VoiceSession
from src.voice.stt import MockSTTProvider, SpeechRecognitionSTTProvider, SpeechToTextProvider, STTError, STTProviderFactory
from src.voice.tts import MockTTSProvider, Pyttsx3TTSProvider, TextToSpeechProvider, TTSError, TTSProviderFactory

__all__ = [
    "AudioConfig",
    "AudioDiagnostics",
    "AudioFrame",
    "MicrophoneManager",
    "MicrophoneUnavailableError",
    "MockSTTProvider",
    "MockTTSProvider",
    "Pyttsx3TTSProvider",
    "STTError",
    "STTProviderFactory",
    "SpeechRecognitionSTTProvider",
    "SpeechToTextProvider",
    "TTSProviderFactory",
    "TextToSpeechProvider",
    "VoiceConfig",
    "VoiceEvent",
    "VoiceEventListener",
    "VoiceManager",
    "VoiceSession",
    "VoiceState",
    "calculate_rms",
    "convert_to_wav",
    "normalize_transcript",
]
