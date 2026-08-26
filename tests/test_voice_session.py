"""
Unit tests for VoiceSession state machine transitions and event routing.
"""

from unittest.mock import MagicMock, patch
from src.brain.agent import AstraAgent
from src.voice.events import VoiceEvent
from src.voice.microphone import MicrophoneManager, MicrophoneUnavailableError
from src.voice.models import VoiceState
from src.voice.session import VoiceSession
from src.voice.stt import MockSTTProvider
from src.voice.tts import MockTTSProvider


@patch("sounddevice.rec")
@patch("sounddevice.wait")
def test_voice_session_turn_success(mock_wait, mock_rec):
    import numpy as np

    mock_rec.return_value = np.zeros((16000, 1), dtype="int16")

    agent = AstraAgent()
    mic = MicrophoneManager()
    stt = MockSTTProvider(mock_transcript="open downloads")
    tts = MockTTSProvider()

    events_received = []

    def on_event(evt, payload):
        events_received.append(evt)

    session = VoiceSession(
        agent=agent,
        microphone_manager=mic,
        stt_provider=stt,
        tts_provider=tts,
        event_listener=on_event,
    )

    response, result = session.listen_and_process(record_seconds=0.1)

    assert result is not None
    assert "Downloads opened" in response
    assert tts.spoken_history[0] == "Downloads opened."
    assert session.state == VoiceState.IDLE
    assert VoiceEvent.LISTENING_STARTED in events_received
    assert VoiceEvent.TRANSCRIPTION_COMPLETED in events_received
    assert VoiceEvent.TTS_COMPLETED in events_received


def test_voice_session_empty_transcript():
    agent = AstraAgent()
    mic = MagicMock()
    mic.record_chunk.return_value = b"fake_silence_pcm"

    stt = MockSTTProvider(mock_transcript="")  # Empty transcript
    tts = MockTTSProvider()

    session = VoiceSession(
        agent=agent,
        microphone_manager=mic,
        stt_provider=stt,
        tts_provider=tts,
    )

    response, result = session.listen_and_process(record_seconds=0.1)

    assert response == "No speech detected."
    assert result is None
    assert session.state == VoiceState.IDLE
    assert len(tts.spoken_history) == 0  # No spoken output for silent capture
