"""
Local Wake Word Detection Engine.
Enables offline, continuous, hands-free 'Hey ASTRA' voice activation without cloud API overhead.
"""

import io
import re
import threading
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable

import speech_recognition as sr
from src.core.config import Config
from src.core.logger import get_logger
from src.voice.audio import calculate_rms, convert_to_wav, normalize_transcript
from src.voice.events import VoiceEvent
from src.voice.models import VoiceState

if TYPE_CHECKING:
    from src.voice.manager import VoiceManager

logger = get_logger()


class WakeWordDetector(ABC):
    """Abstract interface for local wake-word detectors."""

    @abstractmethod
    def detect(self, pcm_data: bytes, sample_rate: int = 16000) -> tuple[bool, str | None]:
        """
        Analyze audio buffer for wake phrase.
        Returns:
            (is_detected: bool, follow_up_command: str | None)
        """
        pass


class LocalWakeWordDetector(WakeWordDetector):
    """
    Local Wake Word Detector for 'Hey ASTRA'.
    Operates offline, evaluating speech energy and matching acoustic/phonetic wake patterns.
    """

    def __init__(
        self,
        wake_phrase: str = "hey astra",
        sensitivity: float = 0.6,
        energy_threshold: float = 120.0,
    ):
        self.wake_phrase = wake_phrase.strip().lower()
        self.sensitivity = sensitivity
        self.energy_threshold = energy_threshold
        self.recognizer = sr.Recognizer()

        # Compile robust regex pattern for 'Hey ASTRA' variations
        # Requires 'hey' (or phonetic equivalent like 'hay', 'hi') + 'astra'
        self.wake_regex = re.compile(
            r"\b(?:hey|hay|hi|ok|okay)?\s*astra\b",
            re.IGNORECASE,
        )
        self.strict_wake_regex = re.compile(
            r"\b(?:hey|hay|hi)[,\s]+\s*astra\b",
            re.IGNORECASE,
        )

    def extract_command(self, raw_text: str) -> tuple[bool, str | None]:
        """
        Check if raw text contains wake phrase and extract any trailing command.
        """
        cleaned = normalize_transcript(raw_text)
        if not cleaned:
            return False, None

        # Check for strict 'hey astra' pattern
        match = self.strict_wake_regex.search(cleaned)
        if not match:
            # Check if exact phrase matches
            if "hey astra" in cleaned.lower() or "hey, astra" in cleaned.lower() or "hey astra," in cleaned.lower():
                match = True
            else:
                return False, None

        # Extract trailing command after the wake phrase
        # E.g. "Hey Astra, open Chrome" -> "open Chrome"
        cmd = re.sub(r"^\s*(?:hey|hay|hi|ok|okay)?[,\s]*\s*astra[,\s]*", "", cleaned, flags=re.IGNORECASE).strip()
        cmd = cmd.strip(" .,!?:;")

        logger.info(f"[WAKE] Positive detection! Transcript: '{cleaned}' -> Extracted command: '{cmd or None}'")
        return True, (cmd if cmd else None)


    def detect(self, pcm_data: bytes, sample_rate: int = 16000) -> tuple[bool, str | None]:
        """Analyze PCM audio bytes for 'Hey ASTRA'."""
        if not pcm_data:
            return False, None

        # Energy gate: Skip background silence / ambient noise immediately
        rms = calculate_rms(pcm_data)
        if rms < self.energy_threshold:
            return False, None

        try:
            wav_bytes = convert_to_wav(pcm_data, sample_rate=sample_rate, channels=1)
            wav_stream = io.BytesIO(wav_bytes)

            with sr.AudioFile(wav_stream) as source:
                audio_data = self.recognizer.record(source)

            # Recognize local speech candidate
            raw_transcript = self.recognizer.recognize_google(audio_data, language="en-US")
            return self.extract_command(raw_transcript)

        except sr.UnknownValueError:
            # Audio contained sound but no decipherable speech
            return False, None
        except Exception as e:
            logger.debug(f"[WAKE] Frame evaluation skipped: {e}")
            return False, None


class MockWakeWordDetector(WakeWordDetector):
    """Deterministic Mock Wake Word Detector for unit testing."""

    def __init__(self, should_detect: bool = False, simulated_command: str | None = None):
        self.should_detect = should_detect
        self.simulated_command = simulated_command

    def detect(self, pcm_data: bytes, sample_rate: int = 16000) -> tuple[bool, str | None]:
        if self.should_detect:
            return True, self.simulated_command
        return False, None


class WakeWordListener:
    """
    Continuous background listener managing the wake-word detection loop and activation lifecycle.
    """

    def __init__(
        self,
        voice_manager: "VoiceManager",
        detector: WakeWordDetector | None = None,
        config: Config | None = None,
    ):
        self.vm = voice_manager
        self.config = config or getattr(voice_manager, "config", Config())
        self.detector = detector or LocalWakeWordDetector(
            wake_phrase=getattr(self.config, "wake_word_phrase", "hey astra"),
            sensitivity=getattr(self.config, "wake_word_sensitivity", 0.6),
        )

        self._running = False
        self._thread: threading.Thread | None = None
        self._suppress_until: float = 0.0
        self._lock = threading.Lock()

    def is_running(self) -> bool:
        """Check if wake word listener thread is actively running."""
        return self._running and self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Start continuous wake word listening in background thread."""
        with self._lock:
            if self._running:
                return

            self._running = True
            self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="AstraWakeWordListener")
            self._thread.start()
            logger.info(f"[WAKE] Wake-word listening active (Phrase: '{getattr(self.config, 'wake_word_phrase', 'hey astra')}')")

    def stop(self) -> None:
        """Stop background wake word listening."""
        with self._lock:
            self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        logger.info("[WAKE] Wake-word listener stopped.")

    def suppress(self, duration_sec: float = 2.0) -> None:
        """Temporarily suppress wake word detection (e.g. during TTS playback to prevent self-trigger)."""
        self._suppress_until = time.time() + duration_sec

    def _listen_loop(self) -> None:
        """Continuous background listening loop."""
        command_timeout = getattr(self.config, "wake_word_command_timeout", 5.0)

        while self._running:
            try:
                # 1. Check if TTS is active or suppression window is active
                if hasattr(self.vm, "tts") and self.vm.tts.is_speaking():
                    time.sleep(0.2)
                    continue

                if time.time() < self._suppress_until:
                    time.sleep(0.2)
                    continue

                # 2. Check if voice session is currently in active conversation / processing
                if self.vm.session.state not in (VoiceState.IDLE, VoiceState.WAKE_WORD_LISTENING):
                    time.sleep(0.2)
                    continue

                # 3. Set State to WAKE_WORD_LISTENING
                if self.vm.session.state != VoiceState.WAKE_WORD_LISTENING:
                    self.vm.session._set_state(VoiceState.WAKE_WORD_LISTENING)
                    self.vm.session.emit_event(VoiceEvent.WAKE_WORD_LISTENING_STARTED)

                # 4. Sample sliding audio frame (1.2 seconds) from microphone
                try:
                    res = self.vm.mic.record_chunk(duration_seconds=1.2)
                    pcm_data, sample_rate = res if isinstance(res, tuple) else (res, 16000)
                except Exception as e:
                    logger.debug(f"[WAKE] Audio frame capture error: {e}")
                    time.sleep(0.5)
                    continue

                # 5. Check if TTS began speaking while recording frame
                if hasattr(self.vm, "tts") and self.vm.tts.is_speaking():
                    continue

                # 6. Analyze frame for 'Hey ASTRA'
                is_detected, follow_up_cmd = self.detector.detect(pcm_data, sample_rate=sample_rate)

                if is_detected:
                    logger.info("[WAKE] Wake word detected! Transitioning to ACTIVE session...")
                    self.vm.session.emit_event(VoiceEvent.WAKE_WORD_DETECTED)

                    # Case A: Wake phrase and command were spoken together in one sentence
                    if follow_up_cmd and len(follow_up_cmd.strip()) > 1:
                        logger.info(f"[WAKE] Direct command found in wake frame: '{follow_up_cmd}'")
                        self.vm.session._set_state(VoiceState.PROCESSING)
                        self.vm.session.emit_event(VoiceEvent.COMMAND_RECEIVED, {"command": follow_up_cmd})

                        # Execute command through ASTRA Core Agent
                        response_text, tool_result = self.vm.agent.process_command(follow_up_cmd)

                        # Speak response via TTS with self-trigger suppression
                        self.suppress(duration_sec=3.0)
                        self.vm.session._set_state(VoiceState.SPEAKING)
                        clean_speech = response_text.replace("✓", "").strip()
                        self.vm.tts.speak(clean_speech)

                        # Return to WAKE_WORD_LISTENING
                        self.vm.session._set_state(VoiceState.WAKE_WORD_LISTENING)
                        continue

                    # Case B: Wake word only ("Hey Astra") -> Listen for follow-up command
                    logger.info(f"[WAKE] Waiting up to {command_timeout:.1f}s for user command...")
                    self.vm.session._set_state(VoiceState.LISTENING)
                    self.vm.session.emit_event(VoiceEvent.LISTENING_STARTED)

                    # Record follow-up command
                    try:
                        cmd_res = self.vm.mic.record_chunk(duration_seconds=min(command_timeout, 4.0))
                        cmd_pcm, cmd_sr = cmd_res if isinstance(cmd_res, tuple) else (cmd_res, 16000)
                    except Exception as e:
                        logger.error(f"[WAKE] Command capture error: {e}")
                        self.vm.session._set_state(VoiceState.WAKE_WORD_LISTENING)
                        continue

                    # Transcribe command
                    transcript = self.vm.stt.transcribe(cmd_pcm, sample_rate=cmd_sr)
                    clean_cmd = transcript.strip() if transcript else ""

                    if not clean_cmd:
                        logger.info("[WAKE] Command timeout: No speech detected following wake word. Returning to idle listening.")
                        self.vm.session.emit_event(VoiceEvent.COMMAND_TIMEOUT)
                        self.vm.session._set_state(VoiceState.WAKE_WORD_LISTENING)
                        continue

                    logger.info(f"[WAKE] Command received: '{clean_cmd}'")
                    self.vm.session._set_state(VoiceState.PROCESSING)
                    self.vm.session.emit_event(VoiceEvent.COMMAND_RECEIVED, {"command": clean_cmd})

                    # Execute command through ASTRA Core Agent
                    response_text, tool_result = self.vm.agent.process_command(clean_cmd)

                    # Speak response via TTS with self-trigger suppression
                    self.suppress(duration_sec=3.0)
                    self.vm.session._set_state(VoiceState.SPEAKING)
                    clean_speech = response_text.replace("✓", "").strip()
                    self.vm.tts.speak(clean_speech)

                    # Return to WAKE_WORD_LISTENING
                    self.vm.session._set_state(VoiceState.WAKE_WORD_LISTENING)

            except Exception as e:
                logger.error(f"[WAKE] Unexpected error in wake-word loop: {e}", exc_info=True)
                time.sleep(0.5)
