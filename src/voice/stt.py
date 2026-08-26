"""
Speech-To-Text (STT) Provider Abstraction and Implementations.
Allows switching STT engines (SpeechRecognition, Whisper, Mock) via provider factory.
"""

from abc import ABC, abstractmethod
import speech_recognition as sr
from src.core.exceptions import AstraError
from src.core.logger import get_logger
from src.voice.audio import convert_to_wav, normalize_transcript

logger = get_logger()


class STTError(AstraError):
    """Exception raised when Speech-To-Text transcription fails."""

    pass


class SpeechToTextProvider(ABC):
    """Abstract interface for Speech-To-Text providers."""

    @abstractmethod
    def transcribe(self, pcm_data: bytes, sample_rate: int = 16000) -> str:
        """Transcribe raw PCM audio bytes to text string."""
        pass


class SpeechRecognitionSTTProvider(SpeechToTextProvider):
    """STT Provider implementation using the speech_recognition package."""

    def __init__(self, language: str = "en-US"):
        self.language = language
        self.recognizer = sr.Recognizer()

    def transcribe(self, pcm_data: bytes, sample_rate: int = 16000) -> str:
        if not pcm_data:
            return ""

        wav_bytes = convert_to_wav(pcm_data, sample_rate=sample_rate)
        audio_file = sr.AudioFile(sr.AudioData(pcm_data, sample_rate, 2))

        try:
            with audio_file as source:
                audio_data = self.recognizer.record(source)

            logger.info("Sending audio to SpeechRecognition engine...")
            raw_transcript = self.recognizer.recognize_google(audio_data, language=self.language)
            cleaned = normalize_transcript(raw_transcript)
            logger.info(f"Transcription successful: '{cleaned}'")
            return cleaned

        except sr.UnknownValueError:
            logger.warning("STT Engine could not understand audio (UnknownValueError)")
            return ""
        except sr.RequestError as e:
            logger.error(f"STT Engine API request error: {e}")
            raise STTError(f"STT provider service error: {e}")
        except Exception as e:
            logger.error(f"STT Transcription failed: {e}")
            raise STTError(f"STT Transcription error: {e}")


class MockSTTProvider(SpeechToTextProvider):
    """Mock STT Provider for deterministic unit testing."""

    def __init__(self, mock_transcript: str = "open calculator"):
        self.mock_transcript = mock_transcript

    def transcribe(self, pcm_data: bytes, sample_rate: int = 16000) -> str:
        return normalize_transcript(self.mock_transcript)


class STTProviderFactory:
    """Factory for creating configured Speech-To-Text providers."""

    @staticmethod
    def create(provider_name: str = "speech_recognition", **kwargs) -> SpeechToTextProvider:
        normalized = provider_name.strip().lower()
        if normalized in ("speech_recognition", "speechrecognition", "default"):
            return SpeechRecognitionSTTProvider(**kwargs)
        elif normalized == "mock":
            return MockSTTProvider(**kwargs)
        else:
            logger.warning(f"Unknown STT provider '{provider_name}'. Falling back to SpeechRecognitionSTTProvider.")
            return SpeechRecognitionSTTProvider(**kwargs)
