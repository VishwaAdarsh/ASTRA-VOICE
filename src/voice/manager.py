"""
Voice Manager Orchestrator.
Coordinates MicrophoneManager, VoiceActivityDetector, STT/TTS Providers, VoiceSession, and ASTRA Core.
"""

from typing import TYPE_CHECKING
from src.core.config import Config
from src.core.logger import get_logger
from src.voice.events import VoiceEvent, VoiceEventListener
from src.voice.microphone import MicrophoneManager
from src.voice.models import AudioConfig, AudioDiagnostics, VoiceConfig, VoiceState
from src.voice.session import VoiceSession
from src.voice.stt import SpeechToTextProvider, STTProviderFactory
from src.voice.tts import TextToSpeechProvider, TTSProviderFactory
from src.voice.vad import VoiceActivityDetector

if TYPE_CHECKING:
    from src.brain.agent import AstraAgent

logger = get_logger()


class VoiceManager:
    """High-level facade and manager for the ASTRA Voice Subsystem."""

    def __init__(
        self,
        agent: "AstraAgent",
        config: Config | None = None,
        stt_provider: SpeechToTextProvider | None = None,
        tts_provider: TextToSpeechProvider | None = None,
        event_listener: VoiceEventListener | None = None,
    ):
        self.agent = agent
        self.config = config or Config()

        # Build audio/voice config
        self.voice_config = VoiceConfig(
            enabled=self.config.voice_enabled,
            stt_provider=self.config.stt_provider,
            tts_provider=self.config.tts_provider,
            microphone_device=self.config.microphone_device,
            tts_rate=self.config.tts_rate,
            tts_volume=self.config.tts_volume,
            voice_language=self.config.voice_language,
            audio=AudioConfig(
                listen_timeout=self.config.listen_timeout,
                silence_timeout=self.config.silence_timeout,
                minimum_speech_duration=self.config.minimum_speech_duration,
            ),
        )

        # Initialize hardware & providers via factories
        self.mic = MicrophoneManager(audio_config=self.voice_config.audio)
        self.vad = VoiceActivityDetector(
            silence_timeout=self.voice_config.audio.silence_timeout,
            minimum_speech_duration=self.voice_config.audio.minimum_speech_duration,
        )

        self.stt = stt_provider or STTProviderFactory.create(
            self.voice_config.stt_provider, language=self.voice_config.voice_language
        )
        self.tts = tts_provider or TTSProviderFactory.create(
            self.voice_config.tts_provider,
            rate=self.voice_config.tts_rate,
            volume=self.voice_config.tts_volume,
        )

        # Initialize Voice Session state machine
        self.session = VoiceSession(
            agent=self.agent,
            microphone_manager=self.mic,
            stt_provider=self.stt,
            tts_provider=self.tts,
            config=self.config,
            event_listener=event_listener,
        )

        logger.info(
            f"VoiceManager initialized (STT={self.voice_config.stt_provider}, TTS={self.voice_config.tts_provider})"
        )

    @property
    def state(self) -> VoiceState:
        """Get current voice state."""
        return self.session.state

    def get_diagnostics(self) -> AudioDiagnostics:
        """Get audio diagnostics for input hardware."""
        return self.mic.get_diagnostics()

    def listen_and_process(self, duration_seconds: float = 3.0):
        """Execute a single voice turn interaction."""
        return self.session.listen_and_process(record_seconds=duration_seconds)

    def speak(self, text: str) -> None:
        """Speak response text aloud."""
        self.tts.speak(text)

    def stop_speaking(self) -> None:
        """Interrupt active speech playback."""
        self.session.stop_speaking()
