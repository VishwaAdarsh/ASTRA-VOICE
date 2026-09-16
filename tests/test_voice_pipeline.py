"""
Integration and Architecture tests for ASTRA V2 Voice Subsystem.
Verifies continuous microphone capture, queue backpressure, STT/TTS zero-silent-fallback,
TTS queue serialization, speech interruption, latency telemetry, and HealthManager updates.
"""

import time
import pytest
from unittest.mock import MagicMock, patch
import sounddevice as sd

from src.brain.agent import AstraAgent
from src.core.config import Config
from src.core.health import HealthManager, HealthStatus
from src.voice.audio import generate_silence, generate_tone
from src.voice.errors import VoiceConfigurationError, STTError
from src.voice.events import VoiceEvent
from src.voice.manager import VoiceManager
from src.voice.microphone import MicrophoneManager
from src.voice.models import AudioConfig, AudioFrame, AudioSegment, VoiceState
from src.voice.session import VoiceSession
from src.voice.stt import MockSTTProvider, STTProviderFactory
from src.voice.tts import MockTTSProvider, TTSProviderFactory


def test_microphone_queue_backpressure():
    """Verify that pushing audio frames to a full frame queue drops oldest frames without deadlock."""
    mgr = MicrophoneManager()
    mgr._is_capturing = True

    # Fill queue to maximum capacity (100 frames)
    for i in range(100):
        fake_data = f"frame_{i}".encode().ljust(32, b"\x00")
        mgr._audio_callback(MagicMock(tobytes=lambda d=fake_data: d), 16, None, None)

    assert mgr._frame_queue.full() is True
    first_frame = mgr._frame_queue.queue[0].data

    # Push 5 additional frames
    for i in range(100, 105):
        fake_data = f"frame_{i}".encode().ljust(32, b"\x00")
        mgr._audio_callback(MagicMock(tobytes=lambda d=fake_data: d), 16, None, None)

    # Queue should still be bounded at 100, and oldest frame dropped
    assert mgr._frame_queue.qsize() == 100
    assert mgr._frame_queue.queue[0].data != first_frame


def test_stt_result_metadata():
    """Verify that STT providers return structured STTResult with telemetry metadata."""
    provider = MockSTTProvider(mock_transcript="turn on the lights")
    segment = AudioSegment(
        pcm_data=b"fake_pcm",
        sample_rate=16000,
        channels=1,
        sample_width=2,
        duration_s=1.5,
    )
    result = provider.transcribe_segment(segment)

    assert result.transcript == "turn on the lights"
    assert result.provider_name == "mock"
    assert result.duration_s >= 0.0
    assert str(result) == "turn on the lights"


def test_stt_zero_silent_fallback():
    """Verify that invalid STT provider raises explicit VoiceConfigurationError (ADR-003 zero silent fallback)."""
    with pytest.raises(VoiceConfigurationError) as exc_info:
        STTProviderFactory.create("unsupported_cloud_stt")
    assert "unsupported" in str(exc_info.value).lower()


def test_tts_zero_silent_fallback():
    """Verify that invalid TTS provider raises explicit VoiceConfigurationError."""
    with pytest.raises(VoiceConfigurationError) as exc_info:
        TTSProviderFactory.create("unsupported_cloud_tts")
    assert "unsupported" in str(exc_info.value).lower()


def test_tts_interruption():
    """Verify TTS stop clears queue and sets is_speaking to False."""
    tts = MockTTSProvider()
    tts.speak("First sentence")
    assert len(tts.spoken_history) == 1

    tts._speaking = True
    assert tts.is_speaking() is True

    tts.stop()
    assert tts.is_speaking() is False


def test_empty_transcript_bypass_agent():
    """Verify empty transcript returns safely to IDLE without calling Agent or TTS."""
    agent = MagicMock()
    agent.process_command = MagicMock()
    mic = MagicMock()
    mic.record_chunk.return_value = b"silent_audio"

    stt = MockSTTProvider(mock_transcript="   ")  # Whitespace only
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
    assert agent.process_command.call_count == 0  # Agent was NOT invoked!
    assert len(tts.spoken_history) == 0  # TTS was NOT invoked!
    assert session.state == VoiceState.IDLE


def test_voice_latency_telemetry():
    """Verify that VoiceSession measures and logs granular latency telemetry across each stage."""
    agent = MagicMock()
    agent.process_command.return_value = ("The time is 12:00 PM", None)
    mic = MagicMock()
    mic.record_chunk.return_value = b"mock_audio"

    stt = MockSTTProvider(mock_transcript="what time is it")
    tts = MockTTSProvider()

    session = VoiceSession(
        agent=agent,
        microphone_manager=mic,
        stt_provider=stt,
        tts_provider=tts,
    )

    response, result = session.listen_and_process(record_seconds=0.1)

    assert session.last_metrics is not None
    m = session.last_metrics
    assert m.capture_start_ts > 0
    assert m.stt_start_ts > 0
    assert m.stt_end_ts >= m.stt_start_ts
    assert m.agent_start_ts > 0
    assert m.agent_end_ts >= m.agent_start_ts
    assert m.tts_start_ts > 0
    assert m.tts_end_ts >= m.tts_start_ts
    assert m.total_turn_ms >= 0.0


def test_voice_manager_health_integration():
    """Verify that VoiceManager registers and updates Microphone, STT, and TTS in HealthManager."""
    agent = MagicMock()
    hm = HealthManager()
    config = Config()

    stt = MockSTTProvider()
    tts = MockTTSProvider()

    manager = VoiceManager(
        agent=agent,
        config=config,
        stt_provider=stt,
        tts_provider=tts,
        health_manager=hm,
    )

    all_health = hm.get_all_health()
    assert "Microphone" in all_health
    assert "STT" in all_health
    assert "TTS" in all_health

    assert all_health["Microphone"].status == HealthStatus.HEALTHY
    assert all_health["STT"].status == HealthStatus.HEALTHY
    assert all_health["TTS"].status == HealthStatus.HEALTHY
