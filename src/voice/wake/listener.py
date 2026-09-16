"""
Continuous Wake-Word Listener Subsystem.
Taps the continuous MicrophoneManager stream, evaluates streaming frames through
the local wake-word detector, manages false-positive suppression, TTS gating,
cooldown periods, and seamless post-wake command capture transitions.
"""

import threading
import time
from typing import TYPE_CHECKING

from src.core.config import Config
from src.core.logger import get_logger
from src.voice.events import VoiceEvent
from src.voice.models import AudioFrame, VoiceState
from src.voice.wake.detector import WakeWordDetector

if TYPE_CHECKING:
    from src.voice.manager import VoiceManager

logger = get_logger()


class WakeWordListener:
    """
    Continuous background listener managing the wake-word detection loop and activation lifecycle.
    """

    def __init__(
        self,
        voice_manager: "VoiceManager",
        detector: WakeWordDetector | None = None,
        config: Config | None = None,
        cooldown_seconds: float = 2.0,
    ):
        self.vm = voice_manager
        self.config = config or getattr(voice_manager, "config", Config())
        self.cooldown_seconds = cooldown_seconds or getattr(self.config, "wake_word_cooldown", 2.0)

        if detector is not None:
            self.detector = detector
        else:
            from src.voice.wake.engine import WakeWordDetectorFactory
            self.detector = WakeWordDetectorFactory.create(self.config)

        self._running = False
        self._thread: threading.Thread | None = None
        self._cooldown_until: float = 0.0
        self._suppress_until: float = 0.0
        self._mic_started_by_listener = False
        self._lock = threading.Lock()

    def is_running(self) -> bool:
        """Check if wake word listener thread is actively running."""
        return self._running and self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Start continuous wake-word listening in background thread."""
        with self._lock:
            if self._running:
                return

            if not getattr(self.config, "wake_word_enabled", True):
                logger.info("[WAKE] Wake-word is disabled in configuration. Listener start aborted.")
                return

            self._running = True
            self.detector.start()
            self._thread = threading.Thread(
                target=self._listen_loop,
                daemon=True,
                name="AstraWakeWordListener",
            )
            self._thread.start()
            logger.info(
                f"[WAKE] Wake-word listening active (Phrase: '{self.detector.wake_phrase}', "
                f"Engine: {self.detector.engine_name})"
            )

    def stop(self) -> None:
        """Stop background wake-word listening."""
        with self._lock:
            self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None
        self.detector.stop()
        if self._mic_started_by_listener and hasattr(self.vm, "mic") and self.vm.mic is not None:
            try:
                if getattr(self.vm.mic, "is_streaming", False):
                    self.vm.mic.stop_stream()
            except Exception:
                pass
            self._mic_started_by_listener = False
        logger.info("[WAKE] Wake-word listener stopped.")

    def suppress(self, duration_sec: float = 2.0) -> None:
        """Temporarily suppress wake-word detection (e.g. during TTS playback)."""
        self._suppress_until = max(self._suppress_until, time.time() + duration_sec)

    def _listen_loop(self) -> None:
        """Continuous background listening loop tapping the continuous microphone stream."""
        command_timeout = getattr(self.config, "wake_word_command_timeout", 5.0)

        # Ensure microphone continuous stream is active
        if hasattr(self.vm, "mic") and self.vm.mic is not None:
            if hasattr(self.vm.mic, "is_streaming") and not self.vm.mic.is_streaming:
                try:
                    self.vm.mic.start_stream()
                    self._mic_started_by_listener = True
                except Exception as e:
                    logger.error(f"[WAKE] Failed to start microphone stream for wake listening: {e}")
                    return

        while self._running:
            try:
                # 1. TTS Gating: Strictly suppress wake detection while ASTRA is speaking
                if hasattr(self.vm, "tts") and self.vm.tts.is_speaking():
                    time.sleep(0.05)
                    continue

                now = time.time()
                # 2. Suppression & Cooldown checks
                if now < self._suppress_until or now < self._cooldown_until:
                    time.sleep(0.05)
                    continue

                # 3. State Check: Only listen when in IDLE, SLEEPING, or WAKE_WORD_LISTENING
                valid_states = (VoiceState.IDLE, VoiceState.SLEEPING, VoiceState.WAKE_WORD_LISTENING)
                if self.vm.session.state not in valid_states:
                    time.sleep(0.05)
                    continue

                # Ensure state is SLEEPING
                if self.vm.session.state != VoiceState.SLEEPING and self.vm.session.state != VoiceState.WAKE_WORD_LISTENING:
                    self.vm.session._set_state(VoiceState.SLEEPING)
                    self.vm.session.emit_event(VoiceEvent.WAKE_WORD_LISTENING_STARTED)

                # 4. Read streaming frame from MicrophoneManager
                frame = self.vm.mic.read_frame(timeout=0.1)
                if frame is None:
                    continue

                # 5. Process frame through local wake-word detector
                result = self.detector.process_audio(frame)

                if result.detected:
                    logger.info(
                        f"[WAKE] Positive detection for '{result.keyword}'! "
                        f"Confidence: {result.confidence}. Transitioning to ACTIVE session..."
                    )

                    # Transition to WAKE_DETECTED state
                    self.vm.session._set_state(VoiceState.WAKE_DETECTED)
                    self.vm.session.emit_event(
                        VoiceEvent.WAKE_WORD_DETECTED,
                        {
                            "keyword": result.keyword,
                            "confidence": result.confidence,
                            "timestamp": result.timestamp,
                        },
                    )

                    # 6. Post-Wake Audio Buffering & Seamless Command Execution
                    if result.extracted_command and len(result.extracted_command.strip()) > 1:
                        # Case A: Wake phrase and command were spoken together
                        cmd = result.extracted_command.strip()
                        logger.info(f"[WAKE] Direct inline command recognized: '{cmd}'")
                        self.vm.session._set_state(VoiceState.PROCESSING)
                        self.vm.session.emit_event(VoiceEvent.COMMAND_RECEIVED, {"command": cmd})

                        response_text, tool_result = self.vm.agent.process_command(cmd)

                        self.suppress(duration_sec=3.0)
                        self.vm.session._set_state(VoiceState.SPEAKING)
                        clean_speech = response_text.replace("✓", "").strip()
                        self.vm.tts.speak(clean_speech)

                    else:
                        # Case B: Wake word detected -> Listen for command with post-wake buffer
                        if result.remaining_pcm:
                            # Prepend preserved post-wake frames to speech segmenter
                            post_frame = AudioFrame(
                                data=result.remaining_pcm,
                                sample_rate=self.vm.mic.config.sample_rate,
                            )
                            self.vm.session.segmenter._pre_roll_buffer.append(post_frame)

                        # Execute interactive voice turn
                        self.vm.session.listen_and_process(timeout=command_timeout)

                    # 7. Apply Cooldown before resuming wake detection
                    self._cooldown_until = time.time() + self.cooldown_seconds
                    self.vm.session._set_state(VoiceState.SLEEPING)

            except Exception as e:
                logger.error(f"[WAKE] Error in wake-word loop: {e}", exc_info=True)
                time.sleep(0.5)
