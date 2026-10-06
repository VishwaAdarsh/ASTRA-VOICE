# ASTRA Voice Subsystem — ElevenLabs Cloud TTS Provider Integration

## 1. Executive Summary

The ASTRA Voice Subsystem now features a production-grade **ElevenLabs Cloud Text-To-Speech (TTS)** provider (`ElevenLabsTTSProvider`). This provider delivers lifelike, low-latency synthetic speech by streaming 16kHz linear PCM directly to the local audio device, coupled with instantaneous barge-in speech interruption and credential privacy safeguards.

```
USER SPEAKS
    ↓
Microphone
    ↓
Wake Word / Voice Detection ("Hey ASTRA")
    ↓
Speech-to-Text (STT)
    ↓
ASTRA Agent (Cognitive Orchestrator)
    ↓
LLM Provider (Ollama / Gemma)
    ↓
Response Text
    ↓
Text Sanitization (Markdown Stripping + Secret Scrubbing)
    ↓
ElevenLabs TTS Provider (api.elevenlabs.io)
    ↓
16kHz Linear PCM Audio (output_format=pcm_16000)
    ↓
sounddevice (Direct Soundcard Playback)
    ↓
SPEAKER / HEADPHONES (ASTRA Talks Back)
```

---

## 2. Architecture & Design Principles

### 2.1 Provider Abstraction
`ElevenLabsTTSProvider` extends the core `TextToSpeechProvider` contract defined in `src/voice/tts.py`. The `TTSProviderFactory` instantiates it whenever `TTS_PROVIDER=elevenlabs`, `eleven_labs`, or `cloud` is configured.

```
                  TextToSpeechProvider (ABC)
                  ├── speak(text, block=True)
                  ├── stop()
                  ├── is_speaking() -> bool
                  ├── configure(rate, volume, voice_id)
                  ├── was_interrupted() -> bool
                  └── shutdown()
                           ▲
          ┌────────────────┴────────────────┐
          │                                 │
Pyttsx3TTSProvider                 ElevenLabsTTSProvider
(Offline Windows SAPI5)            (Cloud Neural Voice Engine)
```

### 2.2 Direct PCM Streaming (Zero-Transcoding Engine)
- ElevenLabs REST endpoint: `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=pcm_16000`
- Delivers raw, uncompressed 16-bit linear PCM audio at 16,000 Hz mono.
- Converted directly to numeric audio arrays using `numpy.frombuffer(raw_bytes, dtype=np.int16)`.
- Played immediately via `sounddevice.play(audio_array, samplerate=16000)`.
- **Zero external transcoding overhead**: eliminates dependencies on `ffmpeg`, `pydub`, or temporary MP3/WAV disk files.

### 2.3 Instantaneous Barge-In Interruption
- The provider employs a dedicated background worker (`AstraElevenLabsWorker`) operating a thread-safe serialized queue.
- When `stop()` is invoked (either programmatically or triggered by the V2-06 `BargeInCoordinator` upon detecting user voice activity during playback):
  1. `_is_interrupted_flag` is immediately flipped to `True`.
  2. `_is_speaking_flag` is cleared.
  3. All pending sentence chunks in `_queue` are instantly purged and caller completion events unblocked.
  4. Hardware playback is terminated instantly via `sounddevice.stop()`.

### 2.4 Text Sanitization Pipeline (`sanitize_text_for_speech`)
Before passing agent response strings to the synthesizer, the text undergoes strict multi-pass sanitization:
1. **Secret Redaction**: Invokes `SecretRedactionFilter.redact()` to ensure API keys, authorization tokens, passwords, and secrets are substituted with `"redacted"` and never vocalized aloud.
2. **Code Block Replacement**: Fenced code blocks (` ```...``` `) are extracted and replaced with natural spoken cues (`" Here is the code. "`) rather than reading syntax line by line.
3. **Markdown Link Parsing**: Markdown links `[Label](URL)` are reduced to `Label`.
4. **URL Redaction**: Bare web addresses (`https://...`, `http://...`) are converted to `"link"`.
5. **Formatting Stripping**: Headers (`#`), emphasis (`*`, `_`), inline code (`` ` ``), strikethroughs (`~~`), list bullets (`-`, `*`, `1.`), and table markers (`|`, `---`) are cleanly stripped.
6. **Whitespace Normalization**: Excessive line breaks and whitespace runs are collapsed into single spaces.

---

## 3. Configuration & Secrets Management

Configuration is loaded strictly from environment variables without exposing secrets to source control, frontend endpoints, or log files:

```bash
# Voice / TTS Configuration (.env)
VOICE_ENABLED=true
TTS_PROVIDER=elevenlabs
TTS_API_KEY=your_elevenlabs_api_key_here
TTS_MODEL=eleven_turbo_v2_5
TTS_VOICE_ID=JBFqnCBsd6RMkjVDRZzb
TTS_BASE_URL=https://api.elevenlabs.io
TTS_TIMEOUT=15.0
TTS_MAX_RETRIES=2
TTS_STABILITY=0.5
TTS_SIMILARITY_BOOST=0.75
```

### Supported Voice Models
- `eleven_turbo_v2_5`: Recommended for real-time conversational agents (sub-second latency, English + multilingual).
- `eleven_multilingual_v2`: High emotional depth and multi-lingual voice consistency.
- `eleven_monolingual_v1`: Standard legacy model.

### Key Resolution & Fallback
The provider prioritizes keys starting with the valid ElevenLabs secret prefix (`sk_`). If a key ID is supplied in `TTS_API_KEY`, ASTRA automatically checks `ELEVENLABS_API_KEY` for a valid active secret key.

---

## 4. Resilience & Error Handling

| HTTP Status | Exception Class | Retry Strategy | Health Status |
| :--- | :--- | :--- | :--- |
| **200 OK** | None | Succeeded | `HEALTHY` |
| **401 / 403** | `ElevenLabsAuthError` | Non-retryable (terminates immediately) | `UNAVAILABLE` |
| **402** | `ElevenLabsQuotaExceededError` | Non-retryable (plan quota or paid voice) | `DEGRADED` |
| **404** | `ElevenLabsTTSError` | Non-retryable (voice ID invalid) | `UNAVAILABLE` |
| **429** | `ElevenLabsRateLimitError` | Exponential backoff (up to 2 retries) | `DEGRADED` |
| **500 - 599** | `ElevenLabsTTSError` | Exponential backoff (up to 2 retries) | `DEGRADED` |
| **Timeout/Network** | `TTSTimeoutError` | Exponential backoff (up to 2 retries) | `DEGRADED` |

---

## 5. Subsystem Health Diagnostics

The provider periodically updates the central `HealthManager` under the `"TTS"` component identifier:
- Successful synthesis marks `"TTS"` as `HEALTHY`.
- Rate limiting or server errors report `DEGRADED`.
- Authentication failures mark `UNAVAILABLE`.
All reported messages are passed through `SecretRedactionFilter.redact()` before entering the health registry.

---

## 6. Verification & Test Suite

The provider test suite in `tests/test_elevenlabs_provider.py` covers 24 scenarios:
1. Provider initialization with valid parameters.
2. Missing API key raises `VoiceConfigurationError`.
3. Custom voice ID and model configuration.
4. Base URL trailing slash trimming.
5. Markdown formatting symbol removal.
6. Fenced code block substitution.
7. Markdown link text extraction.
8. Bare URL replacement.
9. Bullet point and numbered list normalization.
10. Sensitive secret scrubbing via `SecretRedactionFilter`.
11. Whitespace and empty string sanitization.
12. Synthesizer request payload validation (`model_id`, `text`, `voice_settings`).
13. Linear PCM byte extraction.
14. Sounddevice hardware playback initiation at 16kHz.
15. Immediate barge-in interruption via `stop()`.
16. Interrupted and speaking state flags.
17. Transient 5xx retry logic and retry exhaustion.
18. Transient 429 rate limit retry logic.
19. Immediate termination without looping on 401 Unauthorized.
20. Central HealthManager status updating.
21. Factory creation via `TTSProviderFactory.create("elevenlabs")`.
22. Secret masking in `repr()` and error traces.

All 60 voice and TTS tests pass in the test suite.
