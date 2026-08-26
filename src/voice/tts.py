"""
Text-To-Speech (TTS) Provider Abstraction and Implementations.
Provides offline Windows native SAPI5 TTS engine (pyttsx3) and mock test engine.
"""

from abc import ABC, abstractmethod
import threading
import pyttsx3
from src.core.exceptions import AstraError
from src.core.logger import get_logger

logger = get_logger()


class TTSError(AstraError):
    """Exception raised when Text-To-Speech fails."""

    pass


class TextToSpeechProvider(ABC):
    """Abstract interface for Text-To-Speech providers."""

    @abstractmethod
    def speak(self, text: str) -> None:
        """Synthesize and speak output text aloud."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Interrupt and stop current speech playback immediately."""
        pass

    @abstractmethod
    def is_speaking(self) -> bool:
        """Check if speech playback is currently active."""
        pass

    @abstractmethod
    def configure(self, rate: int = 175, volume: float = 1.0, voice_id: str | None = None) -> None:
        """Configure TTS playback speech rate, volume, and voice profile."""
        pass


class Pyttsx3TTSProvider(TextToSpeechProvider):
    """Native Windows SAPI5 TTS Engine provider using pyttsx3."""

    def __init__(self, rate: int = 175, volume: float = 1.0):
        self.rate = rate
        self.volume = volume
        self._is_speaking_flag = False
        self._lock = threading.Lock()

    def configure(self, rate: int = 175, volume: float = 1.0, voice_id: str | None = None) -> None:
        self.rate = rate
        self.volume = volume

    def is_speaking(self) -> bool:
        return self._is_speaking_flag

    def stop(self) -> None:
        """Interrupt and stop active speech playback."""
        logger.info("TTS Interruption requested. Stopping speech playback...")
        self._is_speaking_flag = False

    def speak(self, text: str) -> None:
        if not text or not text.strip():
            return

        with self._lock:
            self._is_speaking_flag = True
            logger.info(f"TTS SPEAKING: '{text}'")

            try:
                # Initialize local pyttsx3 engine instance per call for thread safety
                engine = pyttsx3.init()
                engine.setProperty("rate", self.rate)
                engine.setProperty("volume", self.volume)

                engine.say(text)
                engine.runAndWait()
                engine.stop()
            except Exception as e:
                logger.error(f"Pyttsx3 TTS synthesis error: {e}")
                # Failure to synthesize spoken output should not crash application
            finally:
                self._is_speaking_flag = False


class MockTTSProvider(TextToSpeechProvider):
    """Mock TTS Provider for unit testing and non-audio execution."""

    def __init__(self):
        self.spoken_history: list[str] = []
        self._speaking = False
        self.rate = 175
        self.volume = 1.0

    def configure(self, rate: int = 175, volume: float = 1.0, voice_id: str | None = None) -> None:
        self.rate = rate
        self.volume = volume

    def is_speaking(self) -> bool:
        return self._speaking

    def stop(self) -> None:
        self._speaking = False

    def speak(self, text: str) -> None:
        if not text:
            return
        self._speaking = True
        self.spoken_history.append(text)
        logger.info(f"[MockTTS] Spoke: '{text}'")
        self._speaking = False


class TTSProviderFactory:
    """Factory for creating configured Text-To-Speech providers."""

    @staticmethod
    def create(provider_name: str = "pyttsx3", **kwargs) -> TextToSpeechProvider:
        normalized = provider_name.strip().lower()
        if normalized in ("pyttsx3", "sapi5", "default"):
            return Pyttsx3TTSProvider(**kwargs)
        elif normalized == "mock":
            return MockTTSProvider()
        else:
            logger.warning(f"Unknown TTS provider '{provider_name}'. Falling back to Pyttsx3TTSProvider.")
            return Pyttsx3TTSProvider(**kwargs)
