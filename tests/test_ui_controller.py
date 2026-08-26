"""
Unit tests for AppController signal bridge and non-blocking background workers.
"""

from unittest.mock import MagicMock
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication
from src.brain.agent import AstraAgent
from src.ui.controllers.app_controller import AppController
from src.voice.events import VoiceEvent
from src.voice.manager import VoiceManager
from src.voice.models import VoiceState
from src.voice.stt import MockSTTProvider
from src.voice.tts import MockTTSProvider

_app = QApplication.instance() or QApplication([])


def test_app_controller_submit_text_command():
    agent = AstraAgent()
    voice_manager = VoiceManager(agent=agent, stt_provider=MockSTTProvider(), tts_provider=MockTTSProvider())

    controller = AppController(agent=agent, voice_manager=voice_manager)

    received_commands = []
    responses = []

    controller.sig_command_received.connect(lambda cmd: received_commands.append(cmd))
    controller.sig_response_ready.connect(lambda resp, res: responses.append(resp))

    controller.submit_text_command("open calculator")
    controller.worker.wait()  # Wait for worker thread to finish
    QCoreApplication.processEvents()  # Process pending Qt signals

    assert len(received_commands) == 1
    assert received_commands[0] == "open calculator"
    assert len(responses) == 1
    assert "Calculator opened" in responses[0]
    assert len(controller.activity_history) == 2  # Command + Response entries


def test_app_controller_voice_state_signal():
    agent = AstraAgent()
    voice_manager = VoiceManager(agent=agent, stt_provider=MockSTTProvider(), tts_provider=MockTTSProvider())

    controller = AppController(agent=agent, voice_manager=voice_manager)
    states = []

    controller.sig_voice_state_changed.connect(lambda s: states.append(s))

    # Trigger fake voice event
    controller._on_voice_event(VoiceEvent.LISTENING_STARTED, {"new_state": VoiceState.LISTENING})

    assert len(states) == 1
    assert states[0] == "LISTENING"
