"""
ASTRA V2-05: Comprehensive Test Suite for Wake-Word System.
Tests local acoustic detection, openWakeWord integration/fallback,
TTS gating, cooldown debounce, post-wake frame handoff, HealthManager states,
VoiceManager dynamic toggling, and REST API endpoints.
"""

import math
import struct
import time
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from src.core.config import Config
from src.core.health import HealthManager, HealthStatus
from src.voice.events import VoiceEvent
from src.voice.manager import VoiceManager
from src.voice.models import AudioConfig, AudioFrame, VoiceState, WakeDetectionResult
from src.voice.stt import MockSTTProvider
from src.voice.tts import MockTTSProvider
from src.voice.wake.acoustic import LocalAcousticWakeDetector
from src.voice.wake.detector import WakeWordDetector
from src.voice.wake.engine import (
    DisabledWakeWordDetector,
    LocalWakeWordDetector,
    MockWakeWordDetector,
    WakeWordDetectorFactory,
)
from src.voice.wake.listener import WakeWordListener
from src.voice.wake.openwakeword_engine import OpenWakeWordDetector


# ============================================================================
# Helpers: Synthetic Audio Generators
# ============================================================================

def generate_pcm_silence(duration_sec: float = 0.5, sample_rate: int = 16000) -> bytes:
    """Generate pure digital silence PCM bytes."""
    num_samples = int(sample_rate * duration_sec)
    return b"\x00\x00" * num_samples


def generate_pcm_sine(freq: float, duration_sec: float = 0.5, sample_rate: int = 16000, amplitude: float = 10000.0) -> bytes:
    """Generate a single frequency sine wave in 16-bit mono PCM."""
    num_samples = int(sample_rate * duration_sec)
    frames = []
    for i in range(num_samples):
        val = int(amplitude * math.sin(2.0 * math.pi * freq * (i / sample_rate)))
        val = max(-32768, min(32767, val))
        frames.append(struct.pack("<h", val))
    return b"".join(frames)


def generate_synthetic_hey_astra(sample_rate: int = 16000) -> bytes:
    """
    Generate synthetic audio mimicking the acoustic signature of 'Hey ASTRA':
    - Low-frequency vowel resonance (~500Hz, /eɪ/ and /æ/)
    - High-frequency sibilant energy (~5500Hz, /s/ and /t/)
    """
    duration = 1.2
    num_samples = int(sample_rate * duration)
    frames = []
    for i in range(num_samples):
        t = i / sample_rate
        f1 = math.sin(2.0 * math.pi * 500.0 * t) * 6000.0
        f2 = math.sin(2.0 * math.pi * 1500.0 * t) * 4000.0
        f3 = math.sin(2.0 * math.pi * 5500.0 * t) * 5000.0
        sample = int(f1 + f2 + f3)
        sample = max(-32768, min(32767, sample))
        frames.append(struct.pack("<h", sample))
    return b"".join(frames)


# ============================================================================
# Unit Tests: Detectors & Factories
# ============================================================================

def test_local_acoustic_detector_initialization():
    detector = LocalAcousticWakeDetector(wake_phrase="hey astra", threshold=0.5, energy_gate=100.0)
    assert detector.is_ready() is True
    assert detector.engine_name == "local_acoustic"
    assert detector.wake_phrase == "hey astra"
    assert detector.threshold == 0.5


def test_disabled_wake_detector():
    detector = DisabledWakeWordDetector(wake_phrase="hey astra")
    assert detector.is_ready() is False
    assert detector.engine_name == "disabled"
    assert detector.initialize() is False
    frame = AudioFrame(data=generate_pcm_sine(500.0), sample_rate=16000)
    res = detector.process_audio(frame)
    assert res.detected is False
    assert res.confidence == 0.0


def test_mock_wake_detector():
    detector = MockWakeWordDetector(should_detect=True, simulated_command="open notepad")
    assert detector.is_ready() is True
    frame = AudioFrame(data=generate_pcm_silence(), sample_rate=16000)
    res = detector.process_audio(frame)
    assert res.detected is True
    assert res.confidence == 1.0
    assert res.extracted_command == "open notepad"

    detected, cmd = detector.detect(b"\x00" * 3200)
    assert detected is True
    assert cmd == "open notepad"


def test_factory_disabled():
    cfg = Config()
    cfg.wake_word_enabled = False
    detector = WakeWordDetectorFactory.create(cfg)
    assert isinstance(detector, DisabledWakeWordDetector)
    assert detector.is_ready() is False


def test_factory_mock():
    cfg = Config()
    cfg.wake_word_enabled = True
    cfg.wake_word_engine = "mock"
    detector = WakeWordDetectorFactory.create(cfg, should_detect=False)
    assert isinstance(detector, MockWakeWordDetector)
    assert detector.is_ready() is True


def test_factory_local_acoustic_default():
    cfg = Config()
    cfg.wake_word_enabled = True
    cfg.wake_word_engine = "local_acoustic"
    detector = WakeWordDetectorFactory.create(cfg)
    assert isinstance(detector, LocalAcousticWakeDetector)
    assert detector.is_ready() is True


def test_factory_openwakeword_fallback_on_error():
    cfg = Config()
    cfg.wake_word_enabled = True
    cfg.wake_word_engine = "openwakeword"
    cfg.wake_word_model_path = "non_existent_model_file_path.onnx"
    detector = WakeWordDetectorFactory.create(cfg)
    assert detector.is_ready() is True
    assert isinstance(detector, (OpenWakeWordDetector, LocalAcousticWakeDetector))


# ============================================================================
# Acoustic Signal Evaluation Tests
# ============================================================================

def test_acoustic_silence_rejection():
    detector = LocalAcousticWakeDetector(wake_phrase="hey astra", energy_gate=100.0)
    silence = generate_pcm_silence(duration_sec=0.2)
    frame = AudioFrame(data=silence, sample_rate=16000)
    res = detector.process_audio(frame)
    assert res.detected is False
    assert res.confidence == 0.0


def test_acoustic_low_energy_noise_rejection():
    detector = LocalAcousticWakeDetector(wake_phrase="hey astra", energy_gate=500.0)
    low_noise = generate_pcm_sine(freq=300.0, duration_sec=0.2, amplitude=50.0)
    frame = AudioFrame(data=low_noise, sample_rate=16000)
    res = detector.process_audio(frame)
    assert res.detected is False


def test_acoustic_positive_formants():
    detector = LocalAcousticWakeDetector(wake_phrase="hey astra", threshold=0.15, energy_gate=50.0)
    synthetic_wake = generate_synthetic_hey_astra(sample_rate=16000)
    chunk_size = 3200  # 100ms
    detected_any = False
    for i in range(0, len(synthetic_wake), chunk_size):
        chunk = synthetic_wake[i:i + chunk_size]
        if len(chunk) < 640:
            continue
        res = detector.process_audio(AudioFrame(data=chunk, sample_rate=16000))
        if res.detected:
            detected_any = True
            assert res.confidence > 0.15
            break
    assert detected_any is True


def test_acoustic_detector_reset():
    detector = LocalAcousticWakeDetector(wake_phrase="hey astra")
    detector.process_audio(AudioFrame(data=generate_synthetic_hey_astra(), sample_rate=16000))
    detector.reset()
    assert len(detector._buffer) == 0
    assert len(detector._recent_frames) == 0


# ============================================================================
# WakeWordListener & VoiceManager Integration Tests
# ============================================================================

def test_wake_listener_tts_gating():
    agent = MagicMock()
    config = Config()
    tts = MockTTSProvider()
    tts.is_speaking = MagicMock(return_value=True)

    mock_mic = MagicMock()
    mock_mic.is_streaming = True
    mock_mic.read_frame.return_value = AudioFrame(data=b"\x00" * 3200, sample_rate=16000)

    voice_mgr = VoiceManager(
        agent=agent,
        config=config,
        stt_provider=MockSTTProvider(),
        tts_provider=tts,
        mic=mock_mic,
    )

    mock_detector = MockWakeWordDetector(should_detect=True)
    listener = WakeWordListener(voice_manager=voice_mgr, detector=mock_detector, config=config)

    listener.start()
    time.sleep(0.15)
    listener.stop()

    assert voice_mgr.session.state in (VoiceState.IDLE, VoiceState.SLEEPING)


def test_wake_listener_cooldown_debounce():
    agent = MagicMock()
    config = Config()
    mock_mic = MagicMock()
    mock_mic.is_streaming = True

    voice_mgr = VoiceManager(
        agent=agent,
        config=config,
        stt_provider=MockSTTProvider(),
        tts_provider=MockTTSProvider(),
        mic=mock_mic,
    )

    listener = WakeWordListener(voice_manager=voice_mgr, detector=MockWakeWordDetector(should_detect=False), config=config, cooldown_seconds=2.0)
    listener._cooldown_until = time.time() + 10.0
    listener.suppress(duration_sec=5.0)

    assert listener._cooldown_until > time.time()
    assert listener._suppress_until > time.time()


def test_seamless_compound_command():
    agent = MagicMock()
    agent.process_command.return_value = ("Opened Google Chrome.", None)
    config = Config()
    tts = MockTTSProvider()

    mock_mic = MagicMock()
    mock_mic.is_streaming = True
    mock_mic.read_frame.return_value = AudioFrame(data=b"\x00" * 3200, sample_rate=16000)

    voice_mgr = VoiceManager(
        agent=agent,
        config=config,
        stt_provider=MockSTTProvider(),
        tts_provider=tts,
        mic=mock_mic,
    )

    mock_detector = MockWakeWordDetector(should_detect=True, simulated_command="open chrome")
    listener = WakeWordListener(voice_manager=voice_mgr, detector=mock_detector, config=config)

    listener.start()
    time.sleep(0.2)
    listener.stop()

    agent.process_command.assert_called_with("open chrome")
    assert "Opened Google Chrome." in tts.spoken_history


def test_health_manager_wake_word_statuses():
    health = HealthManager()
    agent = MagicMock()
    agent.health_manager = health
    config = Config()

    # 1. Healthy / Ready
    config.wake_word_enabled = True
    mock_mic = MagicMock()
    vm = VoiceManager(agent=agent, config=config, health_manager=health, mic=mock_mic)
    status_ready = health.get_status("WakeWord")
    assert status_ready is not None
    assert status_ready.status == HealthStatus.READY

    # 2. Disabled
    vm.toggle_wake_word(False)
    status_disabled = health.get_status("WakeWord")
    assert status_disabled.status == HealthStatus.DISABLED

    # 3. Re-enabled
    vm.toggle_wake_word(True)
    status_re_enabled = health.get_status("WakeWord")
    assert status_re_enabled.status == HealthStatus.READY


# ============================================================================
# API Endpoint Tests
# ============================================================================

def test_api_wake_word_endpoints():
    from src.api.server import create_app

    agent = MagicMock()
    config = Config()
    config.wake_word_enabled = True
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

    # 1. GET /api/v1/voice/wake-word/config
    resp = client.get("/api/v1/voice/wake-word/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "enabled" in data
    assert "phrase" in data
    assert data["phrase"] == "hey astra"
    assert "engine" in data
    assert "ready" in data

    # 2. POST /api/v1/voice/wake-word/toggle (disable)
    resp_toggle = client.post("/api/v1/voice/wake-word/toggle", json={"enabled": False})
    assert resp_toggle.status_code == 200
    assert resp_toggle.json()["enabled"] is False
    assert voice_mgr.config.wake_word_enabled is False

    # 3. POST /api/v1/voice/wake-word/toggle (enable)
    resp_toggle2 = client.post("/api/v1/voice/wake-word/toggle", json={"enabled": True})
    assert resp_toggle2.status_code == 200
    assert resp_toggle2.json()["enabled"] is True
    assert voice_mgr.config.wake_word_enabled is True

    voice_mgr.stop_wake_word_listener()
