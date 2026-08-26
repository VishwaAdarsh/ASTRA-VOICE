"""
Unit tests for Text-To-Speech (TTS) Provider Subsystem.
"""

from src.voice.tts import MockTTSProvider, Pyttsx3TTSProvider, TTSProviderFactory


def test_mock_tts_provider():
    provider = MockTTSProvider()
    provider.speak("Calculator is open.")

    assert len(provider.spoken_history) == 1
    assert provider.spoken_history[0] == "Calculator is open."


def test_tts_factory_create():
    mock_p = TTSProviderFactory.create("mock")
    assert isinstance(mock_p, MockTTSProvider)

    pyttsx3_p = TTSProviderFactory.create("pyttsx3")
    assert isinstance(pyttsx3_p, Pyttsx3TTSProvider)
