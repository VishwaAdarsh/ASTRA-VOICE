"""
Voice Manager Orchestrator.
Coordinates MicrophoneManager, VoiceActivityDetector, STT/TTS Providers,
VoiceSession, Subsystem HealthManager, and ASTRA Core.
"""

from typing import TYPE_CHECKING
from src.core.config import Config
from src.core.health import HealthManager, HealthStatus
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
        health_manager: HealthManager | None = None,
        mic: MicrophoneManager | None = None,
    ):
        self.agent = agent
        self.config = config or Config()
        self.health_manager = health_manager or getattr(agent, "health_manager", None)

        # Build audio/voice config with complete V2 parameters
        self.voice_config = VoiceConfig(
            enabled=self.config.voice_enabled,
            stt_provider=self.config.stt_provider,
            tts_provider=self.config.tts_provider,
            microphone_device=self.config.microphone_device,
            tts_rate=self.config.tts_rate,
            tts_volume=self.config.tts_volume,
            voice_language=self.config.voice_language,
            api_key=self.config.voice_api_key,
            audio=AudioConfig(
                sample_rate=getattr(self.config, "voice_sample_rate", 16000),
                channels=getattr(self.config, "voice_channels", 1),
                frame_duration_ms=getattr(self.config, "voice_frame_duration_ms", 30),
                chunk_size=getattr(self.config, "voice_chunk_size", 480),
                listen_timeout=self.config.listen_timeout,
                silence_timeout=getattr(self.config, "silence_timeout", 1.0),
                minimum_speech_duration=getattr(self.config, "minimum_speech_duration", 0.3),
                maximum_utterance_duration=getattr(self.config, "voice_max_utterance_duration", 15.0),
                pre_roll_duration=getattr(self.config, "voice_pre_roll", 0.5),
                post_roll_duration=getattr(self.config, "voice_post_roll", 0.3),
                energy_threshold=getattr(self.config, "voice_energy_threshold", 300.0),
            ),
        )

        # Initialize hardware & providers via factories
        self._mic = mic or MicrophoneManager(audio_config=self.voice_config.audio)
        self.vad = VoiceActivityDetector(
            energy_threshold=self.voice_config.audio.energy_threshold,
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

        # Initialize Local Wake Word Subsystem (Phase V2-05)
        try:
            from src.voice.wake.engine import WakeWordDetectorFactory, WakeWordListener
            self.wake_detector = WakeWordDetectorFactory.create(self.config)
            self.wake_listener = WakeWordListener(
                voice_manager=self,
                detector=self.wake_detector,
                config=self.config,
            )
        except Exception as e:
            logger.warning(f"Wake-word engine initialization error: {e}")
            self.wake_detector = None
            self.wake_listener = None

        # Update initial subsystem health status
        self.update_health()

        logger.info(
            f"VoiceManager initialized (STT={self.voice_config.stt_provider}, "
            f"TTS={self.voice_config.tts_provider}, WakeWord={getattr(self.wake_detector, 'engine_name', 'none')})"
        )

    @property
    def state(self) -> VoiceState:
        """Get current voice state."""
        return self.session.state

    def get_diagnostics(self) -> AudioDiagnostics:
        """Get audio diagnostics for input hardware."""
        return self.mic.get_diagnostics()

    def update_health(self) -> None:
        """Update HealthManager status across Voice Subsystems."""
        if not self.health_manager:
            return

        # 1. Microphone Hardware
        diag = self.get_diagnostics()
        if diag.is_available:
            self.health_manager.set_status(
                "Microphone", HealthStatus.HEALTHY, f"Connected to '{diag.device_name}'"
            )
        else:
            self.health_manager.set_status(
                "Microphone", HealthStatus.UNAVAILABLE, "No functional input device found"
            )

        # 2. STT Engine
        stt_name = getattr(self.stt, "provider_name", self.voice_config.stt_provider)
        self.health_manager.set_status("STT", HealthStatus.HEALTHY, f"Provider: {stt_name}")

        # 3. TTS Engine
        self.health_manager.set_status(
            "TTS", HealthStatus.HEALTHY, f"Provider: {self.voice_config.tts_provider}"
        )

        # 4. Wake Word Subsystem (Phase V2-05)
        if not getattr(self.config, "wake_word_enabled", True):
            self.health_manager.set_status(
                "WakeWord", HealthStatus.DISABLED, "Wake word intentionally disabled in configuration"
            )
        elif self.wake_detector and self.wake_detector.is_ready():
            engine = getattr(self.wake_detector, "engine_name", "local")
            phrase = getattr(self.wake_detector, "wake_phrase", "hey astra")
            self.health_manager.set_status(
                "WakeWord", HealthStatus.READY, f"Active ({engine}: '{phrase}')"
            )
        else:
            self.health_manager.set_status(
                "WakeWord", HealthStatus.UNAVAILABLE, "Wake-word detector unavailable or failed initialization"
            )

    @property
    def mic(self) -> MicrophoneManager:
        return self._mic

    @mic.setter
    def mic(self, value: MicrophoneManager):
        self._mic = value
        if hasattr(self, "session") and self.session is not None:
            self.session.mic = value

    def toggle_wake_word(self, enabled: bool) -> bool:
        """Dynamically enable or disable hands-free wake word listening."""
        self.config.wake_word_enabled = enabled
        if enabled:
            self.start_wake_word_listener()
        else:
            self.stop_wake_word_listener()
            if self.session.state in (VoiceState.SLEEPING, VoiceState.WAKE_WORD_LISTENING):
                self.session._set_state(VoiceState.IDLE)
        self.update_health()
        logger.info(f"[WAKE] Hands-free wake word enabled status set to: {enabled}")
        return self.config.wake_word_enabled

    def start_wake_word_listener(self) -> None:
        """Start continuous hands-free 'Hey ASTRA' background listener."""
        if getattr(self.config, "wake_word_enabled", True) and self.wake_listener:
            self.wake_listener.start()
        self.update_health()

    def stop_wake_word_listener(self) -> None:
        """Stop background wake word listener."""
        if self.wake_listener:
            self.wake_listener.stop()
        self.update_health()

    def listen_and_process(self, duration_seconds: float | None = 3.0):
        """
        Execute a single voice turn interaction (e.g. manual microphone button trigger).
        If duration_seconds is provided, passes to session (or continuous capture if None).
        """
        if self.wake_listener:
            suppress_time = (duration_seconds or 3.0) + 2.0
            self.wake_listener.suppress(duration_sec=suppress_time)
        return self.session.listen_and_process(record_seconds=duration_seconds)

    def speak(self, text: str) -> None:
        """Speak response text aloud with wake-word self-trigger suppression."""
        if self.wake_listener:
            self.wake_listener.suppress(duration_sec=3.0)
        self.tts.speak(text)

    def stop_speaking(self) -> None:
        """Interrupt active speech playback immediately."""
        self.session.stop_speaking()

    def shutdown(self) -> None:
        """Cleanly shutdown voice subsystem and background threads."""
        self.stop_speaking()
        self.stop_wake_word_listener()
        self.mic.stop_stream()
        self.tts.shutdown()
        logger.info("VoiceManager shutdown complete.")
