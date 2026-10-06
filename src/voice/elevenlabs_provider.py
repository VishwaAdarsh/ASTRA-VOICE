"""
ElevenLabs Cloud Text-To-Speech (TTS) Provider.
Delivers ultra-low latency, natural voice responses via ElevenLabs API,
direct 16kHz PCM audio streaming to soundcard, immediate barge-in interruption,
and strict credential protection.
"""

from collections.abc import Generator
import os
import queue
import re
import threading
import time
from typing import Any, Optional

import httpx
import numpy as np

try:
    import sounddevice as sd
except Exception:
    sd = None

from src.core.health import HealthManager, HealthStatus
from src.core.logger import SecretRedactionFilter, get_logger
from src.voice.errors import (
    ElevenLabsAuthError,
    ElevenLabsQuotaExceededError,
    ElevenLabsRateLimitError,
    ElevenLabsTTSError,
    TTSTimeoutError,
    VoiceConfigurationError,
)
from src.voice.tts import TextToSpeechProvider, split_sentences

logger = get_logger()


def sanitize_text_for_speech(text: str) -> str:
    """
    Sanitize text for clean, natural speech synthesis and secret protection.
    - Strips markdown formatting (*, _, ~, #, backticks, tables)
    - Replaces code blocks with natural spoken phrase 'Here is the code.'
    - Strips markdown URLs: [link text](url) -> 'link text'
    - Strips bare URLs: https://... -> 'link'
    - Strips bullet points and list numbering
    - Redacts sensitive credentials (keys, tokens) so they are never spoken aloud
    - Normalizes punctuation and whitespace
    """
    if not text or not text.strip():
        return ""

    # 1. Redact secrets first using SecretRedactionFilter so keys are never spoken
    clean = SecretRedactionFilter.redact(text)
    clean = re.sub(r"\[REDACTED\]", "redacted", clean)

    # 2. Replace fenced code blocks (```...```) with natural spoken indicator
    clean = re.sub(r"```[\s\S]*?```", " Here is the code. ", clean)

    # 3. Replace markdown links [label](url) -> label
    clean = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", clean)

    # 4. Replace bare URLs (http:// or https://) -> 'link'
    clean = re.sub(r"https?://\S+", "link", clean)

    # 5. Remove inline code backticks `code` -> code
    clean = re.sub(r"`([^`]+)`", r"\1", clean)
    clean = clean.replace("`", "")

    # 6. Remove headers (# Header -> Header)
    clean = re.sub(r"#+\s*", "", clean)

    # 7. Remove bold, italic, strikethrough markdown
    clean = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", clean)
    clean = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", clean)
    clean = re.sub(r"~~([^~]+)~~", r"\1", clean)

    # 8. Clean bullet points and numbering at start of lines
    clean = re.sub(r"^\s*[-*+]\s+", "", clean, flags=re.MULTILINE)
    clean = re.sub(r"^\s*\d+\.\s+", "", clean, flags=re.MULTILINE)

    # 9. Clean markdown tables / horizontal dividers
    clean = re.sub(r"\|", " ", clean)
    clean = re.sub(r"[-=]{3,}", " ", clean)

    # 10. Clean excessive whitespace and punctuation
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


class ElevenLabsTTSProvider(TextToSpeechProvider):
    """
    Production ElevenLabs Text-To-Speech Provider.
    Features:
      - 16kHz linear PCM streaming directly to sounddevice with zero transcoding overhead
      - Sentence chunking for fast time-to-first-phoneme playback
      - Real-time barge-in interruption via stop() with queue purging and sounddevice halt
      - Exponential backoff retry logic for transient 5xx and 429 rate limit errors
      - Automatic secret redaction in all logging and exception traces
      - Subsystem health reporting to HealthManager
    """

    DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # George (Free tier friendly)
    DEFAULT_MODEL = "eleven_turbo_v2_5"
    DEFAULT_BASE_URL = "https://api.elevenlabs.io"

    def __init__(
        self,
        api_key: str = "",
        model: str = DEFAULT_MODEL,
        voice_id: str = DEFAULT_VOICE_ID,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 15.0,
        max_retries: int = 2,
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        rate: int = 175,
        volume: float = 1.0,
        health_manager: Optional[HealthManager] = None,
        http_client: Optional[httpx.Client] = None,
        **kwargs: Any,
    ):
        self.model = (model or self.DEFAULT_MODEL).strip()
        self.voice_id = (voice_id or self.DEFAULT_VOICE_ID).strip()
        self.base_url = (base_url or self.DEFAULT_BASE_URL).strip().rstrip("/")
        self.timeout = float(timeout)
        self.max_retries = int(max_retries)
        self.stability = float(stability)
        self.similarity_boost = float(similarity_boost)
        self.rate = rate
        self.volume = max(0.0, min(2.0, float(volume)))
        self.health_manager = health_manager

        # Resolve API Key securely
        resolved_key = (
            api_key
            or os.getenv("TTS_API_KEY", "")
            or os.getenv("ELEVENLABS_API_KEY", "")
            or os.getenv("VOICE_API_KEY", "")
        ).strip()

        # If both TTS_API_KEY and ELEVENLABS_API_KEY exist, check for valid 'sk_' prefix
        if not resolved_key.startswith("sk_"):
            alt_key = os.getenv("ELEVENLABS_API_KEY", "").strip() or os.getenv("VOICE_API_KEY", "").strip()
            if alt_key.startswith("sk_"):
                resolved_key = alt_key

        if not resolved_key:
            raise VoiceConfigurationError(
                "ElevenLabs TTS API key is missing. Set TTS_API_KEY or ELEVENLABS_API_KEY in environment."
            )

        self.api_key = resolved_key

        # HTTP Client management
        self._owned_client = http_client is None
        self._client = http_client or httpx.Client(timeout=self.timeout)

        # Concurrency & Interruption State
        self._queue: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._is_speaking_flag = False
        self._is_interrupted_flag = False
        self._current_done_event: Optional[threading.Event] = None
        self._worker_thread: Optional[threading.Thread] = None

        # Start persistent speech background worker
        self._ensure_worker_started()

    def __repr__(self) -> str:
        masked = f"{self.api_key[:3]}***{self.api_key[-3:]}" if len(self.api_key) > 6 else "***"
        return (
            f"<ElevenLabsTTSProvider voice_id='{self.voice_id}' model='{self.model}' "
            f"base_url='{self.base_url}' api_key='{masked}'>"
        )

    def _update_health(self, status: HealthStatus, message: str) -> None:
        """Update subsystem health if health_manager is provided."""
        if self.health_manager:
            try:
                self.health_manager.set_status("TTS", status, SecretRedactionFilter.redact(message))
            except Exception as e:
                logger.debug(f"Failed to update health status: {e}")

    def _ensure_worker_started(self) -> None:
        """Ensure persistent background worker is active."""
        with self._lock:
            if self._worker_thread is None or not self._worker_thread.is_alive():
                self._stop_event.clear()
                self._worker_thread = threading.Thread(
                    target=self._speech_worker,
                    daemon=True,
                    name="AstraElevenLabsWorker",
                )
                self._worker_thread.start()

    def configure(self, rate: int = 175, volume: float = 1.0, voice_id: Optional[str] = None) -> None:
        """Configure TTS playback speech rate, volume, and voice ID."""
        self.rate = rate
        self.volume = max(0.0, min(2.0, float(volume)))
        if voice_id:
            self.voice_id = voice_id.strip()

    def is_speaking(self) -> bool:
        """Check whether speech playback or queuing is actively in progress."""
        if self._is_interrupted_flag:
            return False
        return self._is_speaking_flag or not self._queue.empty()

    def was_interrupted(self) -> bool:
        """Check whether the active or most recent speech turn was interrupted."""
        return self._is_interrupted_flag

    def clear_interrupted(self) -> None:
        """Clear interrupted state."""
        self._is_interrupted_flag = False

    def stop(self) -> None:
        """
        Interrupt and stop current speech playback immediately:
        - Purges all pending sentence chunks from the queue
        - Unblocks any threads waiting on speech completion
        - Issues immediate hardware stop to sounddevice
        - Signals interruption flag to active worker loops
        """
        logger.info("[TTS] Interruption requested. Stopping ElevenLabs speech playback...")
        with self._lock:
            self._is_interrupted_flag = True
            self._is_speaking_flag = False

            # 1. Drain pending queue and unblock callers
            while not self._queue.empty():
                try:
                    item = self._queue.get_nowait()
                    if item and item[1]:
                        item[1].set()
                except queue.Empty:
                    break

            # 2. Unblock currently speaking item's event
            if self._current_done_event:
                self._current_done_event.set()

            # 3. Halt sounddevice playback immediately
            if sd is not None:
                try:
                    sd.stop()
                except Exception as e:
                    logger.debug(f"[TTS] sounddevice.stop() error: {e}")

    def synthesize(self, text: str) -> bytes:
        """
        Synthesize text to raw 16kHz linear PCM bytes via ElevenLabs API.
        Includes bounded exponential backoff retries on transient errors.
        """
        url = f"{self.base_url}/v1/text-to-speech/{self.voice_id}?output_format=pcm_16000"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/pcm",
        }
        payload = {
            "text": text,
            "model_id": self.model,
            "voice_settings": {
                "stability": self.stability,
                "similarity_boost": self.similarity_boost,
            },
        }

        attempts = 0
        max_attempts = max(1, self.max_retries + 1)
        last_exception: Optional[Exception] = None

        while attempts < max_attempts:
            if self._is_interrupted_flag or self._stop_event.is_set():
                logger.info("[TTS] Synthesis aborted due to interruption.")
                return b""

            attempts += 1
            try:
                logger.debug(f"[TTS] Synthesizing via ElevenLabs (attempt {attempts}/{max_attempts})...")
                response = self._client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )

                if response.status_code == 200:
                    pcm_bytes = response.content
                    self._update_health(HealthStatus.HEALTHY, "ElevenLabs TTS operational")
                    return pcm_bytes

                # Non-retryable authentication error
                if response.status_code in (401, 403):
                    msg = "ElevenLabs authentication failed. Verify TTS_API_KEY / ELEVENLABS_API_KEY."
                    self._update_health(HealthStatus.UNAVAILABLE, msg)
                    raise ElevenLabsAuthError(msg)

                # Non-retryable quota / plan error
                if response.status_code == 402:
                    msg = "ElevenLabs quota exhausted or paid voice requires higher subscription."
                    self._update_health(HealthStatus.DEGRADED, msg)
                    raise ElevenLabsQuotaExceededError(msg)

                # Non-retryable voice not found / bad request
                if response.status_code == 404:
                    msg = f"ElevenLabs voice ID '{self.voice_id}' not found."
                    self._update_health(HealthStatus.UNAVAILABLE, msg)
                    raise ElevenLabsTTSError(msg)

                if response.status_code == 400:
                    try:
                        err_detail = response.json().get("detail", {}).get("message", response.text)
                    except Exception:
                        err_detail = response.text
                    clean_err = SecretRedactionFilter.redact(str(err_detail))
                    msg = f"ElevenLabs Bad Request (400): {clean_err}"
                    self._update_health(HealthStatus.DEGRADED, msg)
                    raise ElevenLabsTTSError(msg)

                # Rate limiting (429) - retryable
                if response.status_code == 429:
                    msg = f"ElevenLabs rate limit exceeded (429) on attempt {attempts}/{max_attempts}."
                    logger.warning(msg)
                    if attempts >= max_attempts:
                        self._update_health(HealthStatus.DEGRADED, "ElevenLabs rate limit exceeded")
                        raise ElevenLabsRateLimitError(msg)
                    backoff = 0.5 * (2 ** (attempts - 1))
                    time.sleep(backoff)
                    continue

                # Server errors (5xx) - retryable
                if 500 <= response.status_code < 600:
                    msg = f"ElevenLabs server error ({response.status_code}) on attempt {attempts}/{max_attempts}."
                    logger.warning(msg)
                    if attempts >= max_attempts:
                        self._update_health(HealthStatus.DEGRADED, f"ElevenLabs server error {response.status_code}")
                        raise ElevenLabsTTSError(msg)
                    backoff = 0.5 * (2 ** (attempts - 1))
                    time.sleep(backoff)
                    continue

                # Unexpected status code
                response.raise_for_status()

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                clean_e = SecretRedactionFilter.redact(str(e))
                last_exception = e
                logger.warning(f"[TTS] Network error on attempt {attempts}/{max_attempts}: {clean_e}")
                if attempts >= max_attempts:
                    self._update_health(HealthStatus.DEGRADED, f"ElevenLabs network failure: {clean_e}")
                    raise TTSTimeoutError(f"ElevenLabs TTS network/timeout failure: {clean_e}") from e
                backoff = 0.5 * (2 ** (attempts - 1))
                time.sleep(backoff)
            except (ElevenLabsAuthError, ElevenLabsQuotaExceededError, ElevenLabsTTSError):
                raise
            except Exception as e:
                clean_e = SecretRedactionFilter.redact(str(e))
                logger.error(f"[TTS] Unexpected synthesis error: {clean_e}")
                self._update_health(HealthStatus.DEGRADED, f"ElevenLabs error: {clean_e}")
                raise ElevenLabsTTSError(f"ElevenLabs synthesis error: {clean_e}") from e

        if last_exception:
            raise ElevenLabsTTSError(f"ElevenLabs synthesis failed: {SecretRedactionFilter.redact(str(last_exception))}")
        return b""

    def _play_pcm_audio(self, pcm_bytes: bytes) -> None:
        """
        Play raw 16kHz linear PCM audio buffer using sounddevice.
        Monitors interruption flag continuously during playback.
        """
        if not pcm_bytes or self._is_interrupted_flag or self._stop_event.is_set():
            return

        # Convert raw linear 16-bit PCM bytes directly into numpy array
        try:
            audio_array = np.frombuffer(pcm_bytes, dtype=np.int16)
        except Exception as e:
            logger.error(f"[TTS] Failed to parse PCM audio buffer: {e}")
            return

        if len(audio_array) == 0:
            return

        # Apply volume scaling if configured
        if self.volume != 1.0:
            audio_array = (audio_array.astype(np.float32) * self.volume).clip(-32768, 32767).astype(np.int16)

        sample_rate = 16000
        duration_s = len(audio_array) / float(sample_rate)

        if sd is not None:
            try:
                sd.play(audio_array, samplerate=sample_rate)
            except Exception as e:
                logger.error(f"[TTS] sounddevice play error: {e}")
                return

            # Wait in small increments while checking for interruption
            elapsed = 0.0
            slice_s = 0.02
            while elapsed < duration_s and not self._is_interrupted_flag and not self._stop_event.is_set():
                time.sleep(slice_s)
                elapsed += slice_s

            if self._is_interrupted_flag:
                try:
                    sd.stop()
                except Exception:
                    pass

    def _speech_worker(self) -> None:
        """Dedicated background worker thread for ElevenLabs synthesis and playback."""
        logger.info("[TTS] AstraElevenLabsWorker started.")
        while not self._stop_event.is_set():
            try:
                item = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if item is None:
                # Sentinel to terminate worker
                break

            sentence, done_event = item
            with self._lock:
                self._current_done_event = done_event

            if not sentence or not sentence.strip() or self._is_interrupted_flag:
                if done_event:
                    done_event.set()
                continue

            self._is_speaking_flag = True
            logger.info(f"TTS SPEAKING (ElevenLabs): '{sentence}'")

            try:
                # 1. Synthesize audio
                pcm_data = self.synthesize(sentence)

                # 2. Play audio if not interrupted
                if pcm_data and not self._is_interrupted_flag:
                    self._play_pcm_audio(pcm_data)

            except Exception as e:
                clean_err = SecretRedactionFilter.redact(str(e))
                logger.error(f"[TTS] Error processing speech chunk: {clean_err}")
            finally:
                if self._queue.empty():
                    self._is_speaking_flag = False
                with self._lock:
                    self._current_done_event = None
                if done_event:
                    done_event.set()

        logger.info("[TTS] AstraElevenLabsWorker terminated.")

    def speak(self, text: str, block: bool = True) -> None:
        """
        Synthesize and speak response text aloud.
        Splits into sentence chunks for responsive interruption.
        If block is True, waits until speech has completed or was interrupted.
        """
        if not text or not text.strip():
            return

        clean_text = sanitize_text_for_speech(text)
        if not clean_text:
            return

        self._ensure_worker_started()
        self._is_interrupted_flag = False
        self._is_speaking_flag = True

        sentences = split_sentences(clean_text)
        if not sentences:
            sentences = [clean_text]

        done_events = []
        for sentence in sentences:
            done_event = threading.Event() if block else None
            if done_event:
                done_events.append(done_event)
            self._queue.put((sentence, done_event))

        if block and done_events:
            last_event = done_events[-1]
            timeout_s = max(5.0, len(clean_text.split()) * 1.0)
            start_t = time.time()
            while not last_event.is_set():
                if self._is_interrupted_flag:
                    break
                if time.time() - start_t > timeout_s:
                    break
                last_event.wait(timeout=0.05)

    def shutdown(self) -> None:
        """Cleanly shutdown TTS worker thread and release HTTP / audio resources."""
        self.stop()
        self._stop_event.set()
        self._queue.put(None)

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)
        self._worker_thread = None

        if self._owned_client:
            try:
                self._client.close()
            except Exception:
                pass
        logger.info("ElevenLabsTTSProvider shutdown complete.")
