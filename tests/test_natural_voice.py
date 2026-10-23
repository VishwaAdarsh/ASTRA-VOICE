"""
End-to-End Natural Voice Conversation Test Suite for ASTRA.
Validates the complete voice conversation pipeline:
Mic -> VAD -> STT -> Agent (Ollama / Gemini) -> TTS -> Barge-In Interruption -> WebSocket UI Synchronization.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.brain.agent import AstraAgent
from src.brain.llm.models import DecisionType, LLMDecision, ModelConfig
from src.core.config import Config
from src.core.events import ASTRAEvent, AstraEventType, EventBus, EventPriority, UIEventAdapter
from src.voice.errors import STTError
from src.voice.events import VoiceEvent
from src.voice.models import AudioConfig, AudioFrame, AudioSegment, VoiceState
from src.voice.session import VoiceSession
from src.voice.stt import MockSTTProvider
from src.voice.tts import MockTTSProvider, sanitize_text_for_speech


@pytest.fixture
def mock_event_bus():
    return EventBus()


@pytest.fixture
def mock_agent(mock_event_bus):
    config = Config()
    config.llm_provider = "mock"
    agent = AstraAgent(config=config)
    agent.event_bus = mock_event_bus
    return agent


@pytest.fixture
def mock_mic():
    mic = MagicMock()
    mic.config = AudioConfig()
    mic.is_streaming = False
    mic.record_chunk.return_value = (b"\x00\x01" * 8000, 16000)
    mic.read_frame.return_value = None
    return mic


@pytest.fixture
def mock_stt():
    return MockSTTProvider(mock_transcript="what is the weather today")


@pytest.fixture
def mock_tts():
    return MockTTSProvider()


@pytest.fixture
def voice_session(mock_agent, mock_mic, mock_stt, mock_tts, mock_event_bus):
    config = Config()
    config.barge_in_enabled = True
    session = VoiceSession(
        agent=mock_agent,
        microphone_manager=mock_mic,
        stt_provider=mock_stt,
        tts_provider=mock_tts,
        config=config,
        event_bus=mock_event_bus,
    )
    return session


def test_end_to_end_voice_turn_success(voice_session, mock_stt, mock_tts, mock_agent):
    """
    Test complete voice interaction turn:
    mic -> STT ("what is the weather today") -> Agent -> TTS speak -> state returns to IDLE.
    """
    mock_stt.set_mock_transcript("what is the weather today")
    with patch.object(
        mock_agent.llm_client.provider,
        "generate_structured",
        return_value=LLMDecision(decision_type=DecisionType.RESPONSE, message="The weather is clear and sunny."),
    ):
        response_text, result = voice_session.listen_and_process(record_seconds=1.0)

    assert "sunny" in response_text.lower()
    assert voice_session.state == VoiceState.IDLE
    assert len(mock_tts.spoken_history) >= 1
    assert "sunny" in mock_tts.spoken_history[-1].lower()


def test_voice_state_transitions_to_event_bus(voice_session, mock_stt, mock_agent, mock_event_bus):
    """
    Verify voice session state machine publishes canonical events to EventBus during a turn.
    """
    published_events = []

    def on_event(evt: ASTRAEvent):
        published_events.append(evt.event_type)

    mock_event_bus.subscribe("*", on_event)
    mock_stt.set_mock_transcript("hello astra")

    with patch.object(
        mock_agent.llm_client.provider,
        "generate_structured",
        return_value=LLMDecision(decision_type=DecisionType.RESPONSE, message="Hello! How can I help you?"),
    ):
        voice_session.listen_and_process(record_seconds=0.5)

    import time
    time.sleep(0.05)

    assert AstraEventType.VOICE_LISTENING_STARTED in published_events
    assert AstraEventType.VOICE_TRANSCRIBING in published_events
    assert AstraEventType.VOICE_SPEAKING_STARTED in published_events
    assert AstraEventType.VOICE_SESSION_ENDED in published_events


def test_ui_event_adapter_broadcasts_voice_state_changed(mock_event_bus):
    """
    Verify UIEventAdapter translates internal voice domain events into standard VOICE_STATE_CHANGED envelopes.
    """
    ws_mock = MagicMock()
    ws_mock.broadcast = AsyncMock()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        adapter = UIEventAdapter(ws_manager=ws_mock, event_bus=mock_event_bus, loop=loop)

        def wait_for_state(expected_state: str, max_wait: float = 0.5) -> None:
            import time
            t0 = time.time()
            while time.time() - t0 < max_wait:
                loop.run_until_complete(asyncio.sleep(0.01))
                calls = [c.args for c in ws_mock.broadcast.call_args_list]
                state_changes = [arg for arg in calls if arg[0] == "VOICE_STATE_CHANGED"]
                if state_changes and state_changes[-1][1]["state"] == expected_state:
                    return
            calls = [c.args for c in ws_mock.broadcast.call_args_list]
            state_changes = [arg for arg in calls if arg[0] == "VOICE_STATE_CHANGED"]
            assert state_changes and state_changes[-1][1]["state"] == expected_state

        # 1. Listening started -> state "listening"
        mock_event_bus.publish(
            ASTRAEvent(event_type=AstraEventType.VOICE_LISTENING_STARTED, source="voice")
        )
        wait_for_state("listening")

        # 2. Transcribing -> state "thinking"
        mock_event_bus.publish(
            ASTRAEvent(event_type=AstraEventType.VOICE_TRANSCRIBING, source="voice")
        )
        wait_for_state("thinking")

        # 3. Speaking -> state "speaking"
        mock_event_bus.publish(
            ASTRAEvent(event_type=AstraEventType.VOICE_SPEAKING_STARTED, source="voice")
        )
        wait_for_state("speaking")

        # 4. Voice interrupted -> state "interrupted"
        mock_event_bus.publish(
            ASTRAEvent(event_type=AstraEventType.VOICE_INTERRUPTED, source="voice")
        )
        wait_for_state("interrupted")

        # 5. Session ended -> state "idle"
        mock_event_bus.publish(
            ASTRAEvent(event_type=AstraEventType.VOICE_SESSION_ENDED, source="voice")
        )
        wait_for_state("idle")

    finally:
        loop.close()


def test_spoken_command_bridges_brain_started_completed(mock_event_bus):
    """
    Verify that when Agent processes a voice command, UIEventAdapter broadcasts BRAIN_STARTED and
    BRAIN_COMPLETED with source='voice', enabling the React UI to display spoken conversation.
    """
    ws_mock = MagicMock()
    ws_mock.broadcast = AsyncMock()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        adapter = UIEventAdapter(ws_manager=ws_mock, event_bus=mock_event_bus, loop=loop)

        # Agent starts voice turn
        mock_event_bus.publish(
            ASTRAEvent(
                event_type=AstraEventType.AGENT_STARTED,
                source="agent",
                request_id="voice-1718000000",
                payload={"input": "open notepad"},
            )
        )
        for _ in range(25):
            calls = [c.args for c in ws_mock.broadcast.call_args_list]
            brain_started = [arg for arg in calls if arg[0] == "BRAIN_STARTED"]
            if brain_started:
                break
            loop.run_until_complete(asyncio.sleep(0.02))

        assert len(brain_started) == 1
        assert brain_started[0][1]["input"] == "open notepad"
        assert brain_started[0][1]["source"] == "voice"

        # Agent completes voice turn
        mock_event_bus.publish(
            ASTRAEvent(
                event_type=AstraEventType.AGENT_COMPLETED,
                source="agent",
                request_id="voice-1718000000",
                payload={"response": "Notepad opened successfully.", "status": "SUCCESS"},
            )
        )
        for _ in range(25):
            calls = [c.args for c in ws_mock.broadcast.call_args_list]
            brain_completed = [arg for arg in calls if arg[0] == "BRAIN_COMPLETED"]
            if brain_completed:
                break
            loop.run_until_complete(asyncio.sleep(0.02))

        assert len(brain_completed) == 1
        assert brain_completed[0][1]["response"] == "Notepad opened successfully."
        assert brain_completed[0][1]["source"] == "voice"

    finally:
        loop.close()


def test_voice_interruption_barge_in(voice_session, mock_tts):
    """
    Verify instant barge-in speech interruption:
    When user interrupts during TTS playback, TTS stops immediately and state transitions to INTERRUPTED.
    """
    mock_tts._speaking = True

    with patch.object(voice_session.barge_in, "monitor_while_speaking", return_value=True):
        with patch.object(voice_session, "_capture_speech_segment", return_value=None):
            resp, _ = voice_session.listen_and_process(record_seconds=0.5)

    assert "interrupted" in resp.lower()
    assert voice_session.state == VoiceState.IDLE


def test_voice_stop_endpoint_cancels_active_session(voice_session, mock_tts):
    """
    Verify stop_speaking() cancels any active session immediately, halts TTS, and sets state to IDLE.
    """
    mock_tts._speaking = True
    voice_session.state = VoiceState.SPEAKING

    voice_session.stop_speaking()

    assert not mock_tts.is_speaking()
    assert voice_session._cancel_requested.is_set()
    assert voice_session.state == VoiceState.IDLE


def test_voice_turn_with_ollama_provider(mock_mic, mock_stt, mock_tts, mock_event_bus):
    """
    Verify voice turn works end-to-end with Ollama provider configured.
    """
    config = Config()
    config.llm_provider = "ollama"
    config.ollama_api_key = "test-ollama-key-secret"
    config.ollama_model = "gemma4:31b"
    config.ollama_base_url = "https://ollama.com"

    mock_ollama_provider = MagicMock()
    mock_ollama_provider.generate_structured.return_value = LLMDecision(
        decision_type=DecisionType.RESPONSE,
        message="Hello from Ollama Gemma! Ready to assist.",
    )

    with patch("src.brain.llm.factory.LLMProviderFactory.create", return_value=mock_ollama_provider):
        agent = AstraAgent(config=config)
        agent.event_bus = mock_event_bus

        session = VoiceSession(
            agent=agent,
            microphone_manager=mock_mic,
            stt_provider=mock_stt,
            tts_provider=mock_tts,
            config=config,
            event_bus=mock_event_bus,
        )

        mock_stt.set_mock_transcript("hello from voice")
        resp, _ = session.listen_and_process(record_seconds=0.5)

        assert "ollama" in resp.lower() or "ready" in resp.lower()
        assert session.state == VoiceState.IDLE
        assert len(mock_tts.spoken_history) >= 1
        assert "ollama" in mock_tts.spoken_history[-1].lower()


def test_voice_empty_speech_returns_idle(voice_session, mock_stt, mock_tts):
    """
    Verify that when no speech is detected or transcript is empty,
    VoiceSession returns cleanly to IDLE without speaking error or crashing.
    """
    mock_stt.set_mock_transcript("")

    resp, res = voice_session.listen_and_process(record_seconds=0.5)

    assert "no speech detected" in resp.lower()
    assert res is None
    assert voice_session.state == VoiceState.IDLE
    assert len(mock_tts.spoken_history) == 0


def test_voice_stt_error_recovery(voice_session, mock_stt, mock_tts):
    """
    Verify that when STT raises an STTError, the session speaks a user-friendly error message
    and returns cleanly to IDLE.
    """
    with patch.object(mock_stt, "transcribe", side_effect=STTError("Transcription network timeout")):
        resp, res = voice_session.listen_and_process(record_seconds=0.5)

    assert "couldn't understand" in resp.lower()
    assert voice_session.state == VoiceState.IDLE
    assert len(mock_tts.spoken_history) >= 1
    assert "couldn't understand" in mock_tts.spoken_history[-1].lower()


def test_voice_turn_secret_scrubbing():
    """
    Verify sensitive API credentials are scrubbed by sanitize_text_for_speech()
    and never vocalized aloud.
    """
    raw_response = (
        "Here is your configuration: GEMINI_API_KEY=AIzaSyD-1234567890abcdef1234567890abc "
        "and TTS_API_KEY=sk_test_1234567890abcdef1234567890abcdef."
    )

    clean = sanitize_text_for_speech(raw_response)

    assert "AIzaSyD" not in clean
    assert "sk_test" not in clean
    assert "redacted" in clean.lower()
