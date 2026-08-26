"""
Unit tests for Speech-To-Text (STT) Provider Subsystem.
"""

from src.voice.stt import MockSTTProvider, SpeechRecognitionSTTProvider, STTProviderFactory


def test_mock_stt_provider():
    provider = MockSTTProvider(mock_transcript="  open calculator  ")
    transcript = provider.transcribe(b"dummy_pcm_bytes")

    assert transcript == "open calculator"


def test_stt_factory_create():
    mock_p = STTProviderFactory.create("mock", mock_transcript="open downloads")
    assert isinstance(mock_p, MockSTTProvider)
    assert mock_p.transcribe(b"") == "open downloads"

    sr_p = STTProviderFactory.create("speech_recognition")
    assert isinstance(sr_p, SpeechRecognitionSTTProvider)
