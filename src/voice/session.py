"""
Voice Session State Machine and Session Orchestration.
Governs state transitions, audio capture, STT transcription, core agent processing, response filtering, and TTS output.
"""

import time
from typing import TYPE_CHECKING, Callable
from src.brain.models import ExecutionStatus, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.voice.events import VoiceEvent, VoiceEventListener
from src.voice.microphone import MicrophoneManager, MicrophoneUnavailableError
from src.voice.models import VoiceConfig, VoiceState
from src.voice.stt import SpeechToTextProvider, STTError
from src.voice.tts import TextToSpeechProvider

if TYPE_CHECKING:
    from src.brain.agent import AstraAgent

logger = get_logger()


class VoiceSession:
    """Manages the state machine and execution workflow of a voice session."""

    def __init__(
        self,
        agent: "AstraAgent",
        microphone_manager: MicrophoneManager,
        stt_provider: SpeechToTextProvider,
        tts_provider: TextToSpeechProvider,
        config: Config | None = None,
        event_listener: VoiceEventListener | None = None,
    ):
        self.agent = agent
        self.mic = microphone_manager
        self.stt = stt_provider
        self.tts = tts_provider
        self.config = config or Config()

        self.state = VoiceState.IDLE
        self.event_listener = event_listener
        self._is_active = False

    def _set_state(self, new_state: VoiceState, details: dict | None = None) -> None:
        """Set voice state and emit log & listener events."""
        old_state = self.state
        self.state = new_state
        logger.info(f"VOICE_STATE: {old_state} -> {new_state}")

        if self.event_listener:
            try:
                # Map state change to corresponding VoiceEvent
                event_type = getattr(VoiceEvent, f"{new_state}_STARTED", VoiceEvent.VOICE_SESSION_STARTED)
                self.event_listener(event_type, {"old_state": old_state, "new_state": new_state, **(details or {})})
            except Exception as e:
                logger.error(f"Error in voice event listener: {e}")

    def emit_event(self, event: VoiceEvent, payload: dict | None = None) -> None:
        """Emit an explicit voice event."""
        if self.event_listener:
            try:
                self.event_listener(event, payload or {})
            except Exception as e:
                logger.error(f"Error emitting event {event}: {e}")

    def listen_and_process(self, record_seconds: float = 3.0) -> tuple[str, ToolResult | None]:
        """Perform a single voice turn: Listen -> STT -> ASTRA Core -> Response -> TTS with timing instrumentation."""
        t_start = time.time()
        try:
            # 1. State: LISTENING
            self._set_state(VoiceState.LISTENING)
            self.emit_event(VoiceEvent.LISTENING_STARTED)

            t_mic_start = time.time()
            try:
                res = self.mic.record_chunk(duration_seconds=record_seconds)
                if isinstance(res, tuple):
                    pcm_data, sample_rate = res
                else:
                    pcm_data, sample_rate = res, getattr(self.mic.config, "sample_rate", 16000)
            except MicrophoneUnavailableError as mue:
                logger.error(f"Microphone error: {mue.message}")
                self._set_state(VoiceState.ERROR, {"error": mue.message})
                self.tts.speak("Microphone is unavailable. Please check your audio input device.")
                self._set_state(VoiceState.IDLE)
                return "Microphone unavailable.", None

            t_mic_end = time.time()
            self.emit_event(VoiceEvent.SPEECH_DETECTED)

            # 2. State: PROCESSING (STT Transcription)
            self._set_state(VoiceState.PROCESSING)
            self.emit_event(VoiceEvent.TRANSCRIPTION_STARTED)

            t_stt_start = time.time()
            try:
                transcript = self.stt.transcribe(pcm_data, sample_rate=sample_rate)
            except STTError as se:
                logger.error(f"STT error during transcription: {se.message}")
                self.emit_event(VoiceEvent.VOICE_ERROR, {"error": se.message})
                self._set_state(VoiceState.SPEAKING)
                error_speech = "I couldn't understand that. Please try again."
                self.tts.speak(error_speech)
                self._set_state(VoiceState.IDLE)
                return error_speech, None

            t_stt_end = time.time()
            stt_latency = t_stt_end - t_stt_start
            self.emit_event(VoiceEvent.TRANSCRIPTION_COMPLETED, {"transcript": transcript})

            # Check for Empty Transcript
            if not transcript or not transcript.strip():
                logger.info("No speech detected in audio capture buffer. Returning to IDLE.")
                self._set_state(VoiceState.IDLE)
                return "No speech detected.", None

            logger.info(f"VOICE TRANSCRIPT: '{transcript}'")
            self.emit_event(VoiceEvent.COMMAND_RECEIVED, {"command": transcript})
            self.emit_event(VoiceEvent.PROCESSING_STARTED)

            # 3. Pass Transcript to ASTRA Core Agent Execution Path
            t_agent_start = time.time()
            response_text, tool_result = self.agent.process_command(transcript)
            t_agent_end = time.time()
            agent_latency = t_agent_end - t_agent_start
            self.emit_event(VoiceEvent.PROCESSING_COMPLETED, {"response": response_text})

            # 4. State: SPEAKING (Route Natural Language Response to TTS)
            self._set_state(VoiceState.SPEAKING)
            self.emit_event(VoiceEvent.TTS_STARTED)

            t_tts_start = time.time()
            # Clean response text for TTS output (strip symbols like ✓)
            clean_speech_text = response_text.replace("✓", "").strip()
            self.tts.speak(clean_speech_text)
            t_tts_end = time.time()
            tts_latency = t_tts_end - t_tts_start

            self.emit_event(VoiceEvent.TTS_COMPLETED)

            # Total Turn Latency
            t_total = time.time() - t_start
            if getattr(self.config, "performance_logging", True):
                logger.info(
                    f"[PERF] Audio Capture: {(t_mic_end - t_mic_start):.2f}s | "
                    f"STT: {stt_latency:.2f}s | "
                    f"LLM/Agent: {agent_latency:.2f}s | "
                    f"TTS: {tts_latency:.2f}s | "
                    f"Total Turn: {t_total:.2f}s"
                )

            # 5. Return to IDLE
            self._set_state(VoiceState.IDLE)
            return response_text, tool_result


        except Exception as e:
            logger.error(f"Unhandled error in VoiceSession loop: {e}", exc_info=True)
            self._set_state(VoiceState.ERROR, {"error": str(e)})
            self.emit_event(VoiceEvent.VOICE_ERROR, {"error": str(e)})
            try:
                self.tts.speak("An error occurred during voice processing.")
            except Exception:
                pass
            self._set_state(VoiceState.IDLE)
            return "An internal voice session error occurred.", None

    def stop_speaking(self) -> None:
        """Interrupt and stop speech playback immediately."""
        self.tts.stop()
        if self.state == VoiceState.SPEAKING:
            self._set_state(VoiceState.IDLE)
