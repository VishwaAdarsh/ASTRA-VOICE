"""
Unit tests for Microphone Hardware Manager.
"""

from unittest.mock import MagicMock, patch
from src.voice.microphone import MicrophoneManager, MicrophoneUnavailableError
from src.voice.models import AudioConfig, AudioDiagnostics


@patch("sounddevice.query_devices")
def test_microphone_discovery(mock_query):
    mock_query.return_value = [
        {"name": "Default Microphone", "max_input_channels": 2, "default_samplerate": 16000},
        {"name": "Headset Mic", "max_input_channels": 1, "default_samplerate": 44100},
    ]

    manager = MicrophoneManager()
    mics = manager.list_microphones()

    assert len(mics) == 2
    assert mics[0]["name"] == "Default Microphone"


@patch("sounddevice.query_devices")
def test_microphone_diagnostics(mock_query):
    mock_query.return_value = [
        {"name": "Studio Microphone", "max_input_channels": 2, "default_samplerate": 48000}
    ]

    manager = MicrophoneManager()
    diag = manager.get_diagnostics()

    assert isinstance(diag, AudioDiagnostics)
    assert diag.is_available is True
    assert diag.device_name == "Studio Microphone"


@patch("sounddevice.rec")
@patch("sounddevice.wait")
def test_microphone_record_chunk_success(mock_wait, mock_rec):
    import numpy as np

    # Mock 1 second of 16-bit PCM zeroes
    fake_audio = np.zeros((16000, 1), dtype="int16")
    mock_rec.return_value = fake_audio

    config = AudioConfig(sample_rate=16000, channels=1)
    manager = MicrophoneManager(audio_config=config)

    chunk = manager.record_chunk(duration_seconds=1.0)
    pcm_data = chunk[0] if isinstance(chunk, tuple) else chunk
    assert isinstance(pcm_data, bytes)
    assert len(pcm_data) == 16000 * 2  # 16-bit = 2 bytes per sample

