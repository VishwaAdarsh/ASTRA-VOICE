"""
ASTRA V2-06: Comprehensive Test Suite for Voice Interruption and Barge-In.
Tests TTS interruptibility, sentence queue serialization and purge,
barge-in detection, false-positive protection (bleed/clicks/grace period),
audio frame preservation, explicit stop commands, concurrency safety,
and REST API endpoints.
"""

import math
import struct
import threading
import time
from unittest.mock import MagicMock, patch
import pytest

from src.core.config import Config
from src.core.health import HealthManager, HealthStatus
from src.voice.barge_in import BargeInCoordinator, BargeInDetector
from src.voice.events import VoiceEvent
from src.voice.manager import VoiceManager
from src.voice.models import AudioFrame, AudioSegment, VoiceMetrics, VoiceState
from src.voice.stt import MockSTTProvider
from src.voice.tts import MockTTSProvider, Pyttsx3TTSProvider, split_sentences


# ============================================================================
# Helpers: Synthetic PCM Audio Generation
# ============================================================================

def generate_pcm_silence(duration_sec: float = 0.5, sample_rate: int = 16000) -> bytes:
    num_samples = int(sample_rate * duration_sec)
    return b"\x00\x00" * num_samples


def generate_pcm_sine(freq: float = 440.0, duration_sec: float = 0.5, sample_rate: int = 16000, amplitude: float = 8000.0) -> bytes:
    num_samples = int(sample_rate * duration_sec)
    frames = []
    for i in range(num_samples):
        val = int(amplitude * math.sin(2.0 * math.pi * freq * (i / sample_rate)))
        val = max(-32768, min(32767, val))
        frames.append(struct.pack("<h", val))
    return b"".join(frames)


# ============================================================================
# 1. TTS Interruptibility & Sentence Chunking Tests
# ============================================================================

def test_split_sentences():
    text = "Hello there! How can I help you today? Here is the current weather forecast."
    chunks = split_sentences(text)
    assert len(chunks) == 3
    assert chunks[0] == "Hello there!"
    assert chunks[1] == "How can I help you today?"
    assert chunks[2] == "Here is the current weather forecast."


def test_split_sentences_empty():
    assert split_sentences("") == []
    assert split_sentences("   ") == []


def test_mock_tts_start_and_stop():
    tts = MockTTSProvider()
    assert tts.is_speaking() is False
    assert tts.was_interrupted() is False

    tts.speak("Testing speech synthesis.")
    assert len(tts.spoken_history) == 1
    assert tts.was_interrupted() is False

    tts.stop()
    assert tts.was_interrupted() is True
    tts.clear_interrupted()
    assert tts.was_interrupted() is False


def test_pyttsx3_stop_and_queue_drain():
    with patch("src.voice.tts.pyttsx3.init", return_value=MagicMock()):
        tts = Pyttsx3TTSProvider()

        # Enqueue multiple sentences
        tts.speak("Sentence one. Sentence two. Sentence three.", block=False)
        assert tts.is_speaking() is True

        # Interrupt and stop
        tts.stop()
        assert tts.was_interrupted() is True
        assert tts._queue.empty() is True
        assert tts.is_speaking() is False

        tts.shutdown()


# ============================================================================
# 2. Barge-In Detection & False-Positive Mitigation Tests
# ============================================================================

def test_barge_in_noise_rejection():
    config = Config()
    config.barge_in_energy_threshold = 650.0
    detector = BargeInDetector(config=config)
    detector.start_monitoring()

    # Low-energy frame (amplitude 200 -> RMS ~140 < 650)
    low_audio = generate_pcm_sine(freq=300.0, duration_sec=0.03, amplitude=200.0)
    frame = AudioFrame(data=low_audio, sample_rate=16000)

    is_interrupted, frames = detector.check_frame(frame, tts_start_ts=time.time() - 1.0)
    assert is_interrupted is False
    assert len(frames) == 0


def test_barge_in_short_click_rejection():
    config = Config()
    config.barge_in_energy_threshold = 500.0
    config.barge_in_min_speech_duration = 0.25
    detector = BargeInDetector(config=config)
    detector.start_monitoring()

    # Single high energy frame (30ms only, less than 250ms requirement)
    loud_click = generate_pcm_sine(freq=1000.0, duration_sec=0.03, amplitude=15000.0)
    frame = AudioFrame(data=loud_click, sample_rate=16000)

    is_interrupted, frames = detector.check_frame(frame, tts_start_ts=time.time() - 1.0)
    assert is_interrupted is False  # Click should not trigger barge-in

    # Followed by silence
    silence = AudioFrame(data=generate_pcm_silence(duration_sec=0.03), sample_rate=16000)
    is_interrupted, _ = detector.check_frame(silence, tts_start_ts=time.time() - 1.0)
    assert is_interrupted is False


def test_barge_in_grace_period():
    config = Config()
    config.barge_in_energy_threshold = 500.0
    config.barge_in_grace_period = 0.3
    detector = BargeInDetector(config=config)
    detector.start_monitoring()

    # Audio occurs immediately as TTS starts (0.05s after TTS start < 0.3s grace period)
    now = time.time()
    tts_start = now - 0.05
    loud_frame = AudioFrame(data=generate_pcm_sine(amplitude=12000.0), sample_rate=16000)

    is_interrupted, _ = detector.check_frame(loud_frame, tts_start_ts=tts_start)
    assert is_interrupted is False


def test_barge_in_positive_detection_and_frame_preservation():
    config = Config()
    config.barge_in_energy_threshold = 500.0
    config.barge_in_min_speech_duration = 0.15  # ~5 frames
    config.barge_in_grace_period = 0.0
    detector = BargeInDetector(config=config)
    detector.start_monitoring()

    tts_start = time.time() - 1.0
    loud_pcm = generate_pcm_sine(freq=400.0, duration_sec=0.03, amplitude=10000.0)
    frame = AudioFrame(data=loud_pcm, sample_rate=16000)

    detected = False
    captured_frames = []
    for _ in range(8):  # 8 * 30ms = 240ms > 150ms
        is_interrupted, frames = detector.check_frame(frame, tts_start_ts=tts_start)
        if is_interrupted:
            detected = True
            captured_frames = frames
            break

    assert detected is True
    assert len(captured_frames) > 0


def test_barge_in_cooldown():
    config = Config()
    config.barge_in_energy_threshold = 500.0
    config.barge_in_min_speech_duration = 0.06
    config.barge_in_cooldown = 1.0
    detector = BargeInDetector(config=config)
    detector.start_monitoring()

    tts_start = time.time() - 1.0
    loud_frame = AudioFrame(data=generate_pcm_sine(amplitude=10000.0, duration_sec=0.03), sample_rate=16000)

    # Trigger first detection
    detector.check_frame(loud_frame, tts_start_ts=tts_start)
    is_int1, _ = detector.check_frame(loud_frame, tts_start_ts=tts_start)
    assert is_int1 is True

    # Re-arm immediately, but cooldown should block
    detector.start_monitoring()
    is_int2, _ = detector.check_frame(loud_frame, tts_start_ts=tts_start)
    assert is_int2 is False


# ============================================================================
# 3. Session Interruption & Command Handling Tests
# ============================================================================

def test_explicit_stop_command():
    agent = MagicMock()
    agent.process_command.return_value = ("Here is a very long speech response.", None)
    config = Config()
    tts = MockTTSProvider()

    mock_mic = MagicMock()
    mock_mic.is_streaming = True

    events = []
    def on_event(evt, payload):
        events.append(evt)

    # Setup STT to simulate user saying "Stop"
    stt = MockSTTProvider(mock_transcript="Stop")

    voice_mgr = VoiceManager(
        agent=agent,
        config=config,
        stt_provider=stt,
        tts_provider=tts,
        event_listener=on_event,
        mic=mock_mic,
    )

    # Simulate barge-in trigger
    voice_mgr.session.barge_in.monitor_while_speaking = MagicMock(return_value=True)
    voice_mgr.session._capture_speech_segment = MagicMock(
        return_value=AudioSegment(
            pcm_data=b"\x00" * 3200,
            sample_rate=16000,
            duration_s=0.2,
        )
    )

    resp, result = voice_mgr.session.listen_and_process(record_seconds=1.0)
    assert resp == "Speech stopped."
    assert result is None
    assert voice_mgr.session.state == VoiceState.IDLE
    voice_mgr.shutdown()


def test_interruption_follow_up_command():
    agent = MagicMock()
    agent.process_command.side_effect = [
        ("Playing long music explanation...", None),
        ("Opened Chrome browser.", None),
    ]
    config = Config()
    tts = MockTTSProvider()
    mock_mic = MagicMock()
    mock_mic.is_streaming = True

    stt = MockSTTProvider(mock_transcript="Open Chrome")
    voice_mgr = VoiceManager(
        agent=agent,
        config=config,
        stt_provider=stt,
        tts_provider=tts,
        mic=mock_mic,
    )

    # Interrupted once, then completes normally
    voice_mgr.session.barge_in.monitor_while_speaking = MagicMock(side_effect=[True, False])
    voice_mgr.session._capture_speech_segment = MagicMock(
        return_value=AudioSegment(pcm_data=b"\x00" * 3200, sample_rate=16000, duration_s=0.2)
    )

    resp, _ = voice_mgr.session.listen_and_process(record_seconds=1.0)
    assert resp == "Opened Chrome browser."
    assert "Opened Chrome browser." in tts.spoken_history
    voice_mgr.shutdown()


def test_session_timeout_after_interruption():
    agent = MagicMock()
    agent.process_command.return_value = ("Initial response.", None)
    config = Config()
    tts = MockTTSProvider()
    mock_mic = MagicMock()
    mock_mic.is_streaming = True

    voice_mgr = VoiceManager(
        agent=agent,
        config=config,
        stt_provider=MockSTTProvider(),
        tts_provider=tts,
        mic=mock_mic,
    )

    voice_mgr.session.barge_in.monitor_while_speaking = MagicMock(return_value=True)
    # User said nothing after interruption (None returned from capture)
    voice_mgr.session._capture_speech_segment = MagicMock(return_value=None)

    resp, result = voice_mgr.session.listen_and_process(record_seconds=1.0)
    assert resp == "Interrupted. No follow-up command."
    assert voice_mgr.session.state == VoiceState.IDLE
    voice_mgr.shutdown()


# ============================================================================
# 4. Health & REST API Endpoint Tests
# ============================================================================

def test_barge_in_health_status():
    health = HealthManager()
    agent = MagicMock()
    agent.health_manager = health
    config = Config()
    mock_mic = MagicMock()

    # 1. Healthy / Ready
    config.barge_in_enabled = True
    vm = VoiceManager(
        agent=agent,
        config=config,
        health_manager=health,
        mic=mock_mic,
        stt_provider=MockSTTProvider(),
        tts_provider=MockTTSProvider(),
    )
    status = health.get_status("BargeIn")
    assert status is not None
    assert status.status == HealthStatus.READY

    # 2. Disabled
    vm.toggle_barge_in(False)
    status_dis = health.get_status("BargeIn")
    assert status_dis.status == HealthStatus.DISABLED

    # 3. Re-enabled
    vm.toggle_barge_in(True)
    status_en = health.get_status("BargeIn")
    assert status_en.status == HealthStatus.READY
    vm.shutdown()


def test_api_barge_in_endpoints():
    from fastapi.testclient import TestClient
    from src.api.server import create_app

    agent = MagicMock()
    config = Config()
    config.barge_in_enabled = True
    mock_mic = MagicMock()
    mock_mic.is_streaming = False

    voice_mgr = VoiceManager(
        agent=agent,
        config=config,
        mic=mock_mic,
        stt_provider=MockSTTProvider(),
        tts_provider=MockTTSProvider(),
    )

    app = create_app(agent=agent, voice_manager=voice_mgr)
    client = TestClient(app)

    # 1. GET /api/v1/voice/barge-in/config
    resp = client.get("/api/v1/voice/barge-in/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "enabled" in data
    assert data["enabled"] is True
    assert "energy_threshold" in data
    assert "min_speech_duration" in data

    # 2. POST /api/v1/voice/barge-in/toggle (disable)
    resp_toggle = client.post("/api/v1/voice/barge-in/toggle", json={"enabled": False})
    assert resp_toggle.status_code == 200
    assert resp_toggle.json()["enabled"] is False
    assert voice_mgr.config.barge_in_enabled is False

    # 3. POST /api/v1/voice/barge-in/toggle (enable)
    resp_toggle2 = client.post("/api/v1/voice/barge-in/toggle", json={"enabled": True})
    assert resp_toggle2.status_code == 200
    assert resp_toggle2.json()["enabled"] is True
    assert voice_mgr.config.barge_in_enabled is True
    voice_mgr.shutdown()


# ============================================================================
# 5. Concurrency Edge Cases (Steps 22)
# ============================================================================

def test_concurrency_case_b_barge_in_with_queued_sentences():
    with patch("src.voice.tts.pyttsx3.init", return_value=MagicMock()):
        tts = Pyttsx3TTSProvider()

        # Queue several sentences
        tts.speak("Sentence one. Sentence two. Sentence three. Sentence four.", block=False)
        assert tts.is_speaking() is True

        # Stop during speech
        tts.stop()
        assert tts.is_speaking() is False
        assert tts._queue.empty() is True
        tts.shutdown()


def test_concurrency_case_c_rapid_double_interruption():
    tts = MockTTSProvider()
    tts._speaking = True
    # Rapid double stop
    tts.stop()
    tts.stop()
    assert tts.was_interrupted() is True
    assert tts.is_speaking() is False


def test_concurrency_case_f_shutdown_while_speaking():
    agent = MagicMock()
    config = Config()
    mock_mic = MagicMock()
    tts = MockTTSProvider()

    vm = VoiceManager(
        agent=agent,
        config=config,
        stt_provider=MockSTTProvider(),
        tts_provider=tts,
        mic=mock_mic,
    )

    tts._speaking = True
    vm.shutdown()
    assert tts.is_speaking() is False
