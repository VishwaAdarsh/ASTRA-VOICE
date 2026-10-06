"""
Unit tests for ElevenLabs Cloud TTS Provider.
Verifies synthesis, text sanitization, streaming PCM playback, interruption (barge-in),
retry logic, error classifications, health tracking, and credential security.
"""

import json
import threading
import time
from unittest.mock import MagicMock, patch

import httpx
import numpy as np
import pytest

from src.core.health import HealthManager, HealthStatus
from src.voice.elevenlabs_provider import ElevenLabsTTSProvider, sanitize_text_for_speech
from src.voice.errors import (
    ElevenLabsAuthError,
    ElevenLabsQuotaExceededError,
    ElevenLabsRateLimitError,
    ElevenLabsTTSError,
    TTSTimeoutError,
    VoiceConfigurationError,
)
from src.voice.tts import TTSProviderFactory


# ---------------------------------------------------------------------------
# Test Helpers & Fixtures
# ---------------------------------------------------------------------------

def create_mock_transport(handler):
    return httpx.MockTransport(handler)


@pytest.fixture
def mock_health_mgr():
    hm = HealthManager()
    return hm


# ---------------------------------------------------------------------------
# 1. Provider Initialization with Valid Config
# ---------------------------------------------------------------------------
def test_provider_initialization_valid_config():
    provider = ElevenLabsTTSProvider(
        api_key="sk_valid_test_key_12345678",
        model="eleven_turbo_v2_5",
        voice_id="JBFqnCBsd6RMkjVDRZzb",
        base_url="https://api.elevenlabs.io",
    )
    assert provider.model == "eleven_turbo_v2_5"
    assert provider.voice_id == "JBFqnCBsd6RMkjVDRZzb"
    assert provider.base_url == "https://api.elevenlabs.io"
    assert provider.api_key == "sk_valid_test_key_12345678"
    provider.shutdown()


# ---------------------------------------------------------------------------
# 2. Provider Initialization Fails Without API Key
# ---------------------------------------------------------------------------
def test_provider_initialization_missing_key(monkeypatch):
    monkeypatch.delenv("TTS_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("VOICE_API_KEY", raising=False)

    with pytest.raises(VoiceConfigurationError) as exc_info:
        ElevenLabsTTSProvider(api_key="")
    assert "ElevenLabs TTS API key is missing" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 3. Custom Voice ID and Model Configuration
# ---------------------------------------------------------------------------
def test_custom_voice_id_and_model():
    provider = ElevenLabsTTSProvider(
        api_key="sk_test_key_12345678",
        model="eleven_multilingual_v2",
        voice_id="custom_voice_abc123",
        stability=0.7,
        similarity_boost=0.85,
    )
    assert provider.voice_id == "custom_voice_abc123"
    assert provider.model == "eleven_multilingual_v2"
    assert provider.stability == 0.7
    assert provider.similarity_boost == 0.85
    provider.shutdown()


# ---------------------------------------------------------------------------
# 4. Base URL Formatting (Stripping Trailing Slash)
# ---------------------------------------------------------------------------
def test_base_url_strips_trailing_slash():
    provider = ElevenLabsTTSProvider(
        api_key="sk_test_key_12345678",
        base_url="https://api.elevenlabs.io///",
    )
    assert provider.base_url == "https://api.elevenlabs.io"
    provider.shutdown()


# ---------------------------------------------------------------------------
# 5. Text Sanitization - Removes Markdown Symbols (*, _, #, `)
# ---------------------------------------------------------------------------
def test_sanitize_removes_markdown_symbols():
    raw = "# Header 1\n## Subheader\nThis is **bold** text and *italic* text with `code_var`!"
    clean = sanitize_text_for_speech(raw)
    assert "#" not in clean
    assert "**" not in clean
    assert "*" not in clean
    assert "`" not in clean
    assert "bold text" in clean
    assert "italic text" in clean
    assert "code_var" in clean


# ---------------------------------------------------------------------------
# 6. Text Sanitization - Handles Code Blocks Gracefully
# ---------------------------------------------------------------------------
def test_sanitize_handles_code_blocks():
    raw = "Here is the solution:\n```python\nimport os\nprint(os.getcwd())\n```\nAll done!"
    clean = sanitize_text_for_speech(raw)
    assert "import os" not in clean
    assert "Here is the code." in clean
    assert "All done!" in clean


# ---------------------------------------------------------------------------
# 7. Text Sanitization - Extracts Link Text from Markdown URLs
# ---------------------------------------------------------------------------
def test_sanitize_extracts_markdown_links():
    raw = "For more information, visit [the official documentation](https://elevenlabs.io/docs) now."
    clean = sanitize_text_for_speech(raw)
    assert "https://elevenlabs.io/docs" not in clean
    assert "the official documentation" in clean


# ---------------------------------------------------------------------------
# 8. Text Sanitization - Replaces Bare URLs
# ---------------------------------------------------------------------------
def test_sanitize_replaces_bare_urls():
    raw = "Check out https://github.com/astral-sh/uv or http://localhost:8000 for status."
    clean = sanitize_text_for_speech(raw)
    assert "https://" not in clean
    assert "http://" not in clean
    assert "link" in clean


# ---------------------------------------------------------------------------
# 9. Text Sanitization - Removes List Bullets and Numbering
# ---------------------------------------------------------------------------
def test_sanitize_removes_list_bullets_and_numbering():
    raw = "Here are your steps:\n* Step one\n- Step two\n1. Step three\n2. Step four"
    clean = sanitize_text_for_speech(raw)
    assert "* " not in clean
    assert "- " not in clean
    assert "1. " not in clean
    assert "2. " not in clean
    assert "Step one" in clean
    assert "Step two" in clean
    assert "Step three" in clean


# ---------------------------------------------------------------------------
# 10. Text Sanitization - Scrubs Secrets via SecretRedactionFilter
# ---------------------------------------------------------------------------
def test_sanitize_scrubs_secrets():
    raw = "Your API key is sk_sample_secret_key_abcdef1234567890 and password is SuperSecretPass123."
    clean = sanitize_text_for_speech(raw)
    assert "sk_sample_secret_key_abcdef1234567890" not in clean
    assert "SuperSecretPass123" not in clean
    assert "redacted" in clean


# ---------------------------------------------------------------------------
# 11. Text Sanitization - Cleans Whitespace and Empty Strings
# ---------------------------------------------------------------------------
def test_sanitize_whitespace_and_empty():
    assert sanitize_text_for_speech("") == ""
    assert sanitize_text_for_speech("   \n\t   ") == ""
    multi_space = "Hello     world. \n\n   This  is   ASTRA."
    assert sanitize_text_for_speech(multi_space) == "Hello world. This is ASTRA."


# ---------------------------------------------------------------------------
# 12. Synthesis Payload Structure (model_id, text, voice_settings)
# ---------------------------------------------------------------------------
def test_synthesis_payload_structure():
    captured_request = {}

    def handler(request: httpx.Request):
        captured_request["url"] = str(request.url)
        captured_request["headers"] = dict(request.headers)
        captured_request["json"] = json.loads(request.content.decode("utf-8"))
        # Return 100 bytes of dummy PCM
        return httpx.Response(200, content=b"\x00" * 100)

    client = httpx.Client(transport=create_mock_transport(handler))
    provider = ElevenLabsTTSProvider(
        api_key="sk_test_payload_12345678",
        model="eleven_turbo_v2_5",
        voice_id="JBFqnCBsd6RMkjVDRZzb",
        http_client=client,
    )

    data = provider.synthesize("Hello from ASTRA!")
    assert len(data) == 100
    assert "output_format=pcm_16000" in captured_request["url"]
    assert captured_request["headers"]["xi-api-key"] == "sk_test_payload_12345678"
    assert captured_request["headers"]["accept"] == "audio/pcm"
    assert captured_request["json"]["text"] == "Hello from ASTRA!"
    assert captured_request["json"]["model_id"] == "eleven_turbo_v2_5"
    assert "stability" in captured_request["json"]["voice_settings"]
    provider.shutdown()


# ---------------------------------------------------------------------------
# 13. Successful Synthesis Audio Chunk Received and Processed
# ---------------------------------------------------------------------------
def test_synthesis_returns_raw_pcm_bytes():
    fake_pcm = (np.sin(np.linspace(0, 100, 3200)) * 10000).astype(np.int16).tobytes()

    def handler(request: httpx.Request):
        return httpx.Response(200, content=fake_pcm)

    client = httpx.Client(transport=create_mock_transport(handler))
    provider = ElevenLabsTTSProvider(
        api_key="sk_test_key_12345678",
        http_client=client,
    )

    pcm = provider.synthesize("Synthesize this audio.")
    assert pcm == fake_pcm
    arr = np.frombuffer(pcm, dtype=np.int16)
    assert len(arr) == 3200
    provider.shutdown()


# ---------------------------------------------------------------------------
# 14. Sounddevice Playback Initiated with 16kHz PCM
# ---------------------------------------------------------------------------
def test_playback_calls_sounddevice():
    fake_pcm = np.zeros(1600, dtype=np.int16).tobytes()

    with patch("src.voice.elevenlabs_provider.sd") as mock_sd:
        mock_sd.play = MagicMock()
        mock_sd.stop = MagicMock()

        def handler(request: httpx.Request):
            return httpx.Response(200, content=fake_pcm)

        client = httpx.Client(transport=create_mock_transport(handler))
        provider = ElevenLabsTTSProvider(
            api_key="sk_test_key_12345678",
            http_client=client,
        )

        provider._play_pcm_audio(fake_pcm)
        assert mock_sd.play.called
        args, kwargs = mock_sd.play.call_args
        assert kwargs.get("samplerate") == 16000 or (len(args) >= 2 and args[1] == 16000)
        provider.shutdown()


# ---------------------------------------------------------------------------
# 15. Immediate Interruption via stop() Halts Sounddevice and Drains Queue
# ---------------------------------------------------------------------------
def test_stop_halts_playback_and_drains_queue():
    with patch("src.voice.elevenlabs_provider.sd") as mock_sd:
        mock_sd.stop = MagicMock()

        provider = ElevenLabsTTSProvider(
            api_key="sk_test_key_12345678",
            http_client=httpx.Client(transport=create_mock_transport(lambda r: httpx.Response(200, content=b"\x00" * 3200))),
        )

        # Enqueue multiple chunks
        event1 = threading.Event()
        event2 = threading.Event()
        provider._queue.put(("Chunk one", event1))
        provider._queue.put(("Chunk two", event2))

        provider.stop()

        assert provider.was_interrupted() is True
        assert provider._queue.empty() is True
        assert event1.is_set() is True
        assert event2.is_set() is True
        assert mock_sd.stop.called is True
        provider.shutdown()


# ---------------------------------------------------------------------------
# 16. is_speaking and was_interrupted State Flags
# ---------------------------------------------------------------------------
def test_speaking_and_interrupted_states():
    provider = ElevenLabsTTSProvider(
        api_key="sk_test_key_12345678",
        http_client=httpx.Client(transport=create_mock_transport(lambda r: httpx.Response(200, content=b""))),
    )
    assert provider.is_speaking() is False
    assert provider.was_interrupted() is False

    provider._is_speaking_flag = True
    assert provider.is_speaking() is True

    provider.stop()
    assert provider.is_speaking() is False
    assert provider.was_interrupted() is True

    provider.clear_interrupted()
    assert provider.was_interrupted() is False
    provider.shutdown()


# ---------------------------------------------------------------------------
# 17. Retry Logic on Transient 5xx Server Errors
# ---------------------------------------------------------------------------
def test_retry_on_5xx_server_error():
    call_count = 0

    def handler(request: httpx.Request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(502, content=b"Bad Gateway")
        return httpx.Response(200, content=b"PCM_DATA")

    client = httpx.Client(transport=create_mock_transport(handler))
    provider = ElevenLabsTTSProvider(
        api_key="sk_test_key_12345678",
        max_retries=2,
        http_client=client,
    )

    data = provider.synthesize("Retry test.")
    assert data == b"PCM_DATA"
    assert call_count == 2
    provider.shutdown()


def test_repeated_5xx_exhausts_retries():
    def handler(request: httpx.Request):
        return httpx.Response(500, content=b"Internal Server Error")

    client = httpx.Client(transport=create_mock_transport(handler))
    provider = ElevenLabsTTSProvider(
        api_key="sk_test_key_12345678",
        max_retries=1,
        http_client=client,
    )

    with pytest.raises(ElevenLabsTTSError) as exc_info:
        provider.synthesize("Should fail after retry.")
    assert "ElevenLabs server error (500)" in str(exc_info.value)
    provider.shutdown()


# ---------------------------------------------------------------------------
# 18. Retry Logic on 429 Rate Limit Errors
# ---------------------------------------------------------------------------
def test_retry_on_429_rate_limit():
    call_count = 0

    def handler(request: httpx.Request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(429, content=b"Too Many Requests")
        return httpx.Response(200, content=b"PCM_DATA_AFTER_429")

    client = httpx.Client(transport=create_mock_transport(handler))
    provider = ElevenLabsTTSProvider(
        api_key="sk_test_key_12345678",
        max_retries=2,
        http_client=client,
    )

    data = provider.synthesize("Rate limit retry test.")
    assert data == b"PCM_DATA_AFTER_429"
    assert call_count == 2
    provider.shutdown()


def test_persistent_429_raises_rate_limit_error():
    def handler(request: httpx.Request):
        return httpx.Response(429, content=b"Too Many Requests")

    client = httpx.Client(transport=create_mock_transport(handler))
    provider = ElevenLabsTTSProvider(
        api_key="sk_test_key_12345678",
        max_retries=1,
        http_client=client,
    )

    with pytest.raises(ElevenLabsRateLimitError):
        provider.synthesize("Will fail 429.")
    provider.shutdown()


# ---------------------------------------------------------------------------
# 19. Non-Retryable 401 Unauthorized Raises Auth Error Without Looping
# ---------------------------------------------------------------------------
def test_401_raises_auth_error_no_retry():
    call_count = 0

    def handler(request: httpx.Request):
        nonlocal call_count
        call_count += 1
        return httpx.Response(401, content=b"Unauthorized")

    client = httpx.Client(transport=create_mock_transport(handler))
    provider = ElevenLabsTTSProvider(
        api_key="sk_invalid_key_12345678",
        max_retries=2,
        http_client=client,
    )

    with pytest.raises(ElevenLabsAuthError):
        provider.synthesize("Invalid key test.")
    assert call_count == 1  # Exactly 1 call, zero retries
    provider.shutdown()


# ---------------------------------------------------------------------------
# 20. Health Manager Updated on Success and Failure
# ---------------------------------------------------------------------------
def test_health_manager_integration(mock_health_mgr):
    # Test healthy on 200
    client_ok = httpx.Client(transport=create_mock_transport(lambda r: httpx.Response(200, content=b"PCM")))
    provider_ok = ElevenLabsTTSProvider(
        api_key="sk_test_key_12345678",
        health_manager=mock_health_mgr,
        http_client=client_ok,
    )
    provider_ok.synthesize("Healthy check.")
    assert mock_health_mgr.get_status("TTS").status == HealthStatus.HEALTHY
    provider_ok.shutdown()

    # Test unavailable on 401
    client_fail = httpx.Client(transport=create_mock_transport(lambda r: httpx.Response(401, content=b"Unauthorized")))
    provider_fail = ElevenLabsTTSProvider(
        api_key="sk_test_key_12345678",
        health_manager=mock_health_mgr,
        http_client=client_fail,
    )
    with pytest.raises(ElevenLabsAuthError):
        provider_fail.synthesize("Auth check.")
    assert mock_health_mgr.get_status("TTS").status == HealthStatus.UNAVAILABLE
    provider_fail.shutdown()


# ---------------------------------------------------------------------------
# 21. Factory Instantiation and Provider Registration
# ---------------------------------------------------------------------------
def test_factory_creates_elevenlabs():
    provider = TTSProviderFactory.create(
        "elevenlabs",
        api_key="sk_factory_test_key_12345678",
    )
    assert isinstance(provider, ElevenLabsTTSProvider)
    provider.shutdown()

    provider_alias = TTSProviderFactory.create(
        "cloud",
        api_key="sk_factory_test_key_12345678",
    )
    assert isinstance(provider_alias, ElevenLabsTTSProvider)
    provider_alias.shutdown()


# ---------------------------------------------------------------------------
# 22. Secret Redaction in Repr
# ---------------------------------------------------------------------------
def test_secret_masked_in_repr():
    secret = "sk_sample_secret_key_abcdef1234567890"
    provider = ElevenLabsTTSProvider(api_key=secret)
    rep = repr(provider)
    assert secret not in rep
    assert "sk_***" in rep or "***" in rep
    provider.shutdown()
