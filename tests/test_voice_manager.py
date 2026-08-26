"""
Integration tests for VoiceManager orchestrator.
"""

from unittest.mock import MagicMock
from src.brain.agent import AstraAgent
from src.brain.models import ExecutionStatus
from src.voice.manager import VoiceManager
from src.voice.models import VoiceState
from src.voice.stt import MockSTTProvider
from src.voice.tts import MockTTSProvider


def test_voice_manager_end_to_end_flow():
    agent = AstraAgent()
    mock_stt = MockSTTProvider(mock_transcript="show system information")
    mock_tts = MockTTSProvider()

    manager = VoiceManager(agent=agent, stt_provider=mock_stt, tts_provider=mock_tts)

    # Mock microphone to return dummy audio buffer
    manager.mic.record_chunk = MagicMock(return_value=b"dummy_pcm_audio")

    response, result = manager.listen_and_process(duration_seconds=0.1)

    assert result is not None
    assert result.status == ExecutionStatus.SUCCESS
    assert "Operating System" in response
    assert len(mock_tts.spoken_history) == 1
    assert "Operating System" in mock_tts.spoken_history[0]
    assert manager.state == VoiceState.IDLE
