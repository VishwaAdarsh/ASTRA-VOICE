"""
Unit and Integration tests for Local Wake Word Engine ('Hey ASTRA') and Hands-Free Voice Subsystem.
"""

import time
from unittest.mock import MagicMock, patch
import pytest

from src.core.config import Config
from src.brain.agent import AstraAgent
from src.brain.models import ExecutionStatus, ToolResult
from src.voice.events import VoiceEvent
from src.voice.manager import VoiceManager
from src.voice.models import VoiceState
from src.voice.stt import MockSTTProvider
from src.voice.tts import MockTTSProvider
from src.voice.wake.engine import (
    LocalWakeWordDetector,
    MockWakeWordDetector,
    WakeWordListener,
)


def test_wake_word_detector_positive_phrase():
    detector = LocalWakeWordDetector(wake_phrase="hey astra")

    # 1. Simple Wake phrase
    is_detected, cmd = detector.extract_command("Hey Astra")
    assert is_detected is True
    assert cmd is None

    # 2. Case variations & punctuation
    is_detected2, cmd2 = detector.extract_command("hey ASTRA,")
    assert is_detected2 is True

    is_detected3, cmd3 = detector.extract_command("Hey, Astra!")
    assert is_detected3 is True


def test_wake_word_detector_compound_sentence():
    detector = LocalWakeWordDetector(wake_phrase="hey astra")

    # Wake phrase + immediate command
    is_detected, cmd = detector.extract_command("Hey Astra, open Chrome")
    assert is_detected is True
    assert cmd == "open Chrome"

    is_detected2, cmd2 = detector.extract_command("Hey Astra open my Downloads folder.")
    assert is_detected2 is True
    assert cmd2 == "open my Downloads folder"


def test_wake_word_detector_negative_rejections():
    detector = LocalWakeWordDetector(wake_phrase="hey astra")

    # 1. Completely unrelated speech
    is_detected1, cmd1 = detector.extract_command("Today is a beautiful sunny day.")
    assert is_detected1 is False
    assert cmd1 is None

    # 2. 'Astra' without 'Hey'
    is_detected2, cmd2 = detector.extract_command("Astra is a nice word.")
    assert is_detected2 is False
    assert cmd2 is None


def test_wake_word_listener_lifecycle():
    agent = MagicMock()
    config = Config()
    voice_mgr = VoiceManager(agent=agent, config=config, stt_provider=MockSTTProvider(), tts_provider=MockTTSProvider())

    mock_detector = MockWakeWordDetector(should_detect=False)
    listener = WakeWordListener(voice_manager=voice_mgr, detector=mock_detector, config=config)

    assert listener.is_running() is False
    listener.start()
    assert listener.is_running() is True
    time.sleep(0.1)

    listener.stop()
    assert listener.is_running() is False

    # Restart
    listener.start()
    assert listener.is_running() is True
    listener.stop()
    assert listener.is_running() is False


def test_wake_word_tts_suppression():
    agent = MagicMock()
    config = Config()
    tts = MockTTSProvider()
    voice_mgr = VoiceManager(agent=agent, config=config, stt_provider=MockSTTProvider(), tts_provider=tts)

    listener = WakeWordListener(voice_manager=voice_mgr, detector=MockWakeWordDetector(should_detect=False), config=config)

    # Trigger suppression
    listener.suppress(duration_sec=2.0)
    assert listener._suppress_until > time.time()


def test_wake_word_command_timeout():
    agent = AstraAgent()
    config = Config()
    config.wake_word_command_timeout = 0.2

    events = []
    def on_event(evt, payload):
        events.append(evt)

    stt = MockSTTProvider(mock_transcript="")  # Silence after wake word
    tts = MockTTSProvider()
    mic = MagicMock()
    mic.record_chunk.return_value = (b"\x00" * 3200, 16000)

    voice_mgr = VoiceManager(agent=agent, config=config, stt_provider=stt, tts_provider=tts, event_listener=on_event)
    voice_mgr.mic = mic

    mock_detector = MockWakeWordDetector(should_detect=True, simulated_command=None)
    listener = WakeWordListener(voice_manager=voice_mgr, detector=mock_detector, config=config)

    listener.start()
    time.sleep(0.4)
    listener.stop()

    # Verify transition back to idle without calling agent
    assert VoiceEvent.WAKE_WORD_DETECTED in events
    assert VoiceEvent.COMMAND_TIMEOUT in events
    assert len(tts.spoken_history) == 0
