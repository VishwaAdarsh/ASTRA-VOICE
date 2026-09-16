"""
Text-To-Speech (TTS) Provider Abstraction and Implementations.
Provides persistent Windows SAPI5 engine lifecycle management via pyttsx3,
a serialized background speech queue, and foundation for speech interruption.
"""

from abc import ABC, abstractmethod
import queue
import threading
import time
import pyttsx3

from src.core.logger import get_logger
from src.voice.errors import TTSError, TTSTimeoutError, VoiceConfigurationError

logger = get_logger()


class TextToSpeechProvider(ABC):
    """Abstract interface for Text-To-Speech providers."""

    @abstractmethod
    def speak(self, text: str, block: bool = True) -> None:
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

    def shutdown(self) -> None:
        """Release audio resources and terminate background workers."""
        pass


class Pyttsx3TTSProvider(TextToSpeechProvider):
    """
    Persistent SAPI5 TTS Engine provider using pyttsx3.
    Maintains a persistent engine instance in a dedicated speech worker thread
    with a serialized queue to prevent concurrent overlapping utterances.
    """

    def __init__(self, rate: int = 175, volume: float = 1.0):
        self.rate = rate
        self.volume = volume
        self._is_speaking_flag = False
        self._queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._engine = None
        self._lock = threading.Lock()

        # Start persistent background speech worker
        self._ensure_worker_started()

    def _ensure_worker_started(self) -> None:
        """Ensure the persistent speech worker thread is running."""
        with self._lock:
            if self._worker_thread is None or not self._worker_thread.is_alive():
                self._stop_event.clear()
                self._worker_thread = threading.Thread(
                    target=self._speech_worker,
                    daemon=True,
                    name="AstraTTSWorker",
                )
                self._worker_thread.start()

    def _speech_worker(self) -> None:
        """Dedicated background worker thread for pyttsx3 SAPI5 engine execution."""
        try:
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self.rate)
            self._engine.setProperty("volume", self.volume)
        except Exception as e:
            logger.warning(f"Failed to initialize pyttsx3 SAPI5 engine in worker thread: {e}")
            self._engine = None

        while not self._stop_event.is_set():
            try:
                item = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if item is None:
                # Sentinel to terminate worker
                break

            text, done_event = item
            if not text or not text.strip():
                if done_event:
                    done_event.set()
                continue

            self._is_speaking_flag = True
            logger.info(f"TTS SPEAKING: '{text}'")

            try:
                if self._engine is None:
                    self._engine = pyttsx3.init()
                    self._engine.setProperty("rate", self.rate)
                    self._engine.setProperty("volume", self.volume)

                self._engine.say(text)
                self._engine.runAndWait()
            except Exception as e:
                logger.error(f"Pyttsx3 TTS synthesis error: {e}")
                self._engine = None
            finally:
                self._is_speaking_flag = False
                if done_event:
                    done_event.set()

    def configure(self, rate: int = 175, volume: float = 1.0, voice_id: str | None = None) -> None:
        """Configure TTS playback speech rate and volume."""
        self.rate = rate
        self.volume = volume
        if self._engine:
            try:
                self._engine.setProperty("rate", self.rate)
                self._engine.setProperty("volume", self.volume)
                if voice_id:
                    self._engine.setProperty("voice", voice_id)
            except Exception as e:
                logger.debug(f"Failed to update TTS properties: {e}")

    def is_speaking(self) -> bool:
        """Check whether speech playback is currently active."""
        return self._is_speaking_flag or not self._queue.empty()

    def stop(self) -> None:
        """Interrupt and stop active speech playback immediately and purge queue."""
        logger.info("TTS Interruption requested. Stopping speech playback...")
        # 1. Drain pending queue
        while not self._queue.empty():
            try:
                item = self._queue.get_nowait()
                if item and item[1]:
                    item[1].set()
            except queue.Empty:
                break

        # 2. Halt current playback if active
        if self._engine:
            try:
                self._engine.stop()
            except Exception as e:
                logger.debug(f"Error calling engine.stop(): {e}")
        self._is_speaking_flag = False

    def speak(self, text: str, block: bool = True) -> None:
        """
        Synthesize speech text. If block is True, waits until speech has completed.
        If block is False, enqueues speech for background playback.
        """
        if not text or not text.strip():
            return

        self._ensure_worker_started()
        done_event = threading.Event() if block else None
        self._queue.put((text, done_event))

        if block and done_event:
            # Wait for utterance completion with a reasonable safety timeout
            timeout_s = max(5.0, len(text.split()) * 0.8)
            done_event.wait(timeout=timeout_s)

    def shutdown(self) -> None:
        """Cleanly shutdown TTS worker thread and release SAPI5 engine."""
        self.stop()
        self._stop_event.set()
        self._queue.put(None)
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)
        self._worker_thread = None
        self._engine = None
        logger.info("Pyttsx3TTSProvider shutdown complete.")


class MockTTSProvider(TextToSpeechProvider):
    """Mock TTS Provider for deterministic unit testing and non-audio environments."""

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

    def speak(self, text: str, block: bool = True) -> None:
        if not text:
            return
        self._speaking = True
        self.spoken_history.append(text)
        logger.info(f"[MockTTS] Spoke: '{text}'")
        self._speaking = False

    def shutdown(self) -> None:
        self.stop()


class TTSProviderFactory:
    """Factory for creating configured Text-To-Speech providers with zero silent fallback."""

    @staticmethod
    def create(provider_name: str = "pyttsx3", **kwargs) -> TextToSpeechProvider:
        normalized = provider_name.strip().lower()
        if normalized in ("pyttsx3", "sapi5", "default"):
            return Pyttsx3TTSProvider(**kwargs)
        elif normalized == "mock":
            return MockTTSProvider()
        else:
            raise VoiceConfigurationError(
                f"Unknown or unsupported TTS provider '{provider_name}'. "
                "Supported providers are: 'pyttsx3', 'mock'."
            )
