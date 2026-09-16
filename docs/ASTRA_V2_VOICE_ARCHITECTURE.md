# ASTRA V2 — Voice Engine Architecture

**Phase:** V2-04  
**Status:** Canonical  
**Date:** 2026-09-16  

---

## 1. Executive Summary & Architecture Overview

Phase V2-04 establishes a low-latency, modular, and resilient voice processing subsystem for ASTRA V2. The previous architecture captured audio in fixed-duration blocking windows (e.g. `sd.rec(4.0)` + `sd.wait()`), forcing users to wait multiple seconds even for brief commands like "open Chrome".

The new architecture operates on continuous microphone streaming, energy-based Voice Activity Detection (VAD) with adaptive noise tracking, and rolling pre-roll buffered speech segmentation. Audio is segmented on natural trailing silence and forwarded immediately to Speech-to-Text (STT), cutting voice response turnaround times dramatically.

```
┌─────────────────────────────────────────────────────────────┐
│                    Microphone Hardware                      │
│             (Windows DirectSound / WASAPI / MME)            │
└──────────────────────────────┬──────────────────────────────┘
                               │ Continuous InputStream (16kHz, 16-bit Mono)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                      MicrophoneManager                      │
│  - Continuous InputStream callback                          │
│  - Bounded Frame Queue (100 frames max, backpressure safe)  │
│  - Hardware device discovery & diagnostics                  │
└──────────────────────────────┬──────────────────────────────┘
                               │ AudioFrames (30ms chunks = 480 samples = 960 bytes)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│              SpeechSegmenter & VoiceActivityDetector        │
│  - Rolling Pre-Roll Buffer (0.5s audio history)             │
│  - Adaptive noise floor estimation                          │
│  - Speech Onset Trigger (VADState.SPEECH_START)             │
│  - Trailing Silence Detection (1.0s timeout)                │
│  - Maximum Utterance Guard (15.0s hard cap)                 │
│  - Minimum Speech Filter (rejects < 0.3s noise clicks)      │
└──────────────────────────────┬──────────────────────────────┘
                               │ AudioSegment (PCM bytes + duration + timestamps)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 SpeechToTextProvider (STT)                  │
│  - SpeechRecognition (Google STT) / MockSTT                 │
│  - Empty / whitespace transcript detection & bypass         │
│  - Explicit error reporting (no silent mock fallback)       │
│  - STTResult container with duration & telemetry metadata   │
└──────────────────────────────┬──────────────────────────────┘
                               │ Clean Normalized Transcript
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                   AstraAgent (Brain Subsystem)              │
│  - LLM Subsystem / Cognitive Intent Extraction              │
│  - Safe Tool Execution & Verification                       │
└──────────────────────────────┬──────────────────────────────┘
                               │ Natural Language Response Text
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 TextToSpeechProvider (TTS)                  │
│  - Persistent pyttsx3 SAPI5 engine in dedicated worker      │
│  - Serialized Thread Queue (prevents overlapping speech)    │
│  - Clean speech interruption foundation (stop() / purge)    │
│  - Safe resource release on engine shutdown                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Voice State Machine

The voice subsystem is governed by an explicit 8-state finite state machine (`src/voice/models.py`):

```
       ┌───────────────────────────────┐
       │             IDLE              │◄───────────────────────┐
       └──────────────┬────────────────┘                        │
                      │ Listen Trigger                          │
                      ▼                                         │
       ┌───────────────────────────────┐                        │
       │           LISTENING           │                        │
       └──────────────┬────────────────┘                        │
                      │ Speech Energy Detected                  │
                      ▼                                         │
       ┌───────────────────────────────┐                        │
       │        SPEECH_DETECTED        │                        │
       └──────────────┬────────────────┘                        │
                      │ Start Accumulating Utterance            │
                      ▼                                         │
       ┌───────────────────────────────┐                        │
       │           CAPTURING           │                        │
       └──────────────┬────────────────┘                        │
                      │ Trailing Silence (1.0s) / Max Utterance │
                      ▼                                         │
       ┌───────────────────────────────┐                        │
       │          PROCESSING           │                        │
       │  (STT Transcribe + Agent LLM) │                        │
       └──────────────┬────────────────┘                        │
                      │ Natural Language Response Generated     │
                      ▼                                         │
       ┌───────────────────────────────┐                        │
       │           SPEAKING            │                        │
       │     (TTS Output Queue)        │                        │
       └──────────────┬────────────────┘                        │
                      │ Speech Playback Finished                │
                      └─────────────────────────────────────────┘

Exceptional Transitions:
- LISTENING (Timeout without speech) ──────────────► IDLE
- CAPTURING / PROCESSING (STT Empty / Noise) ─────► IDLE
- SPEAKING (Interrupted via stop()) ──────────────► INTERRUPTED ──► IDLE
- Hardware / Service Failure ──────────────────────► ERROR ────────► IDLE
```

### State Definitions:
- `IDLE`: Microphone stream is idle or paused. Subsystem is ready for command triggers.
- `LISTENING`: Continuous stream is actively buffering frames and scanning for voice energy.
- `SPEECH_DETECTED`: Energy threshold exceeded; rolling pre-roll buffer is locked into the speech buffer.
- `CAPTURING`: Active utterance buffering in progress.
- `PROCESSING`: Utterance finalized; Speech-to-Text and AstraAgent cognitive execution underway.
- `SPEAKING`: Text-to-Speech synthesis and audio output active.
- `INTERRUPTED`: User or system interrupted speech playback before completion.
- `ERROR`: Subsystem error state; reports diagnostic telemetry and cleans up resources.

---

## 3. Continuous Audio Capture & Bounded Queue

### 3.1 Stream Lifecycle (`MicrophoneManager`)
- **No Per-Utterance Allocations:** Rather than opening and tearing down audio devices for every command, `MicrophoneManager` initializes `sounddevice.InputStream` and maintains continuous frame delivery.
- **Methods:**
  - `start_stream()`: Activates the continuous background capture stream.
  - `stop_stream()`: Halts stream and drains queued frames.
  - `pause_stream()`: Pauses delivery during TTS playback to prevent self-capture.
  - `resume_stream()`: Resumes frame delivery once playback ceases.
  - `read_frame(timeout=0.1)`: Retrieves the next buffered `AudioFrame`.
  - `get_diagnostics()`: Returns live hardware status, channels, sample rate, and availability.

### 3.2 Backpressure & Bounded Buffering
To prevent unbounded memory growth in high-load scenarios:
- Audio frame queue is strictly bounded at **100 frames** (~3 seconds of audio).
- If the downstream consumer falls behind and the queue fills up, `MicrophoneManager` drops the oldest frame (`get_nowait()`) and logs a diagnostic warning rather than blocking the real-time audio thread or leaking RAM.

---

## 4. Voice Activity Detection & Speech Segmentation

### 4.1 VoiceActivityDetector (`src/voice/vad.py`)
- **Signal-Level Operation:** Operates purely on raw PCM data without knowledge of UI, Agent, or LLMs.
- **Adaptive Noise Floor:** Tracks background room acoustic baseline using moving average (`alpha = 0.05`). Adjusts the active speech threshold dynamically when ambient noise fluctuates.

### 4.2 SpeechSegmenter (`src/voice/segmenter.py`)
- **Pre-Roll Buffer:** Maintains a rolling circular queue (`collections.deque`) holding the most recent **0.5s** of audio frames prior to speech onset. When `SPEECH_START` is triggered, the pre-roll frames are prepended to the utterance buffer, guaranteeing that initial plosives and vowels are never cut off.
- **Trailing Silence Threshold:** Utterance completion is declared when trailing silence reaches **1.0s** (configurable via `VOICE_SILENCE_TIMEOUT`).
- **Maximum Utterance Guard:** Speech capture is strictly capped at **15.0s** (`VOICE_MAX_UTTERANCE_DURATION`) to protect against stuck VAD states, continuous background noise, or memory bloat.
- **Short Noise Discard:** Speech segments with net vocal duration under **0.3s** (`VOICE_MIN_SPEECH_DURATION`) are discarded as clicks, mic bumps, or coughs, returning directly to silence without burdening the LLM.

---

## 5. Resilient STT & TTS Providers

### 5.1 Speech-to-Text (STT)
- **Metadata Container (`STTResult`):** Returns transcribed text along with duration, confidence (if supported), language, and provider name.
- **Empty Transcript Handling:** If STT produces an empty or whitespace-only string (e.g. ambient breath sounds), `VoiceSession` safely aborts agent dispatch and returns to `IDLE` state.
- **Prohibition of Silent Mock Fallback (ADR-003):** `STTProviderFactory` validates provider names strictly. In production, STT connection failures raise typed `STTError` and update `HealthManager` rather than silently degrading to `MockSTTProvider`.

### 5.2 Text-to-Speech (TTS)
- **Persistent Engine Lifecycle:** `Pyttsx3TTSProvider` initializes the Windows SAPI5 COM engine once inside a dedicated background worker thread (`AstraTTSWorker`), eliminating the severe latency overhead of re-initializing the engine per sentence.
- **Serialized Worker Queue:** Speech requests are enqueued into a thread-safe `queue.Queue`. Utterances are spoken sequentially without audio clipping or thread deadlocks.
- **Interruption Foundation:** `stop()` purges pending utterances from the queue and halts current SAPI5 playback via `engine.stop()`.

---

## 6. Subsystem Health Integration & Telemetry

### 6.1 Health Diagnostics (`HealthManager`)
`VoiceManager` registers and continuously reports operational status across three voice subsystems:
- `Microphone`: `HEALTHY` (connected & streaming) or `UNAVAILABLE` (hardware disconnected / access denied).
- `STT`: `HEALTHY` (provider responsive) or `DEGRADED` / `UNAVAILABLE` (network or service failure).
- `TTS`: `HEALTHY` (engine initialized & ready) or `UNAVAILABLE` (audio output failure).

### 6.2 Latency Telemetry (`VoiceMetrics`)
For every voice interaction, `VoiceSession` tracks fine-grained execution timestamps:
- `capture_start_ts`: Initial trigger / listening start.
- `speech_detected_ts`: Timestamp when vocal energy crossed threshold.
- `speech_end_ts`: Timestamp when trailing silence finalized the utterance.
- `stt_start_ts` / `stt_end_ts`: Duration spent in speech-to-text decoding.
- `agent_start_ts` / `agent_end_ts`: Duration spent in cognitive reasoning and tool execution.
- `tts_start_ts` / `tts_end_ts`: Latency to first spoken phoneme and total audio playback.
- **Calculated Telemetry:**
  - `speech_to_stt_ms`: Latency from speech end to STT initiation.
  - `stt_latency_ms`: STT engine transcription duration.
  - `agent_latency_ms`: Agent LLM + Tool execution duration.
  - `tts_startup_latency_ms`: Delay before TTS begins audio output.
  - `total_turn_ms`: Complete user utterance to assistant response turnaround time.

Benchmark results show the VAD and segmentation pipeline processes 1,000 frames (30 seconds of audio) in **28.22 ms** (Real-Time Factor: **0.00094**), operating over 1,000x faster than real-time with negligible CPU overhead.

---

## 7. Configuration Reference

All voice audio parameters are centralized in `AudioConfig` (`src/voice/models.py`) and configurable via environment variables:

| Environment Variable | Default | Description |
| :--- | :--- | :--- |
| `VOICE_ENABLED` | `true` | Enable or disable voice subsystem. |
| `STT_PROVIDER` | `speech_recognition` | Active STT engine (`speech_recognition`, `mock`). |
| `TTS_PROVIDER` | `pyttsx3` | Active TTS engine (`pyttsx3`, `mock`). |
| `VOICE_SAMPLE_RATE` | `16000` | PCM audio sample rate in Hz. |
| `VOICE_CHANNELS` | `1` | Audio input channel count (1 = Mono). |
| `VOICE_FRAME_DURATION` | `30` | Frame buffer duration in milliseconds. |
| `VOICE_SILENCE_TIMEOUT` | `1.0` | Seconds of trailing silence required to end speech. |
| `VOICE_MIN_SPEECH_DURATION` | `0.3` | Minimum seconds of speech required to accept utterance. |
| `VOICE_MAX_UTTERANCE_DURATION`| `15.0` | Maximum recording duration cap in seconds. |
| `VOICE_PRE_ROLL` | `0.5` | Rolling audio buffer duration before speech trigger. |
| `VOICE_POST_ROLL` | `0.3` | Post-roll audio padding duration in seconds. |
| `VOICE_ENERGY_THRESHOLD` | `300.0` | Base RMS vocal energy detection threshold. |
| `VOICE_INPUT_DEVICE` | `default` | Input hardware device name or index. |
| `VOICE_OUTPUT_DEVICE` | `default` | Output hardware device name or index. |
| `TTS_RATE` | `175` | Speech synthesis rate (words per minute). |
| `TTS_VOLUME` | `1.0` | Speech synthesis volume (0.0 to 1.0). |
| `VOICE_LANGUAGE` | `en-US` | Spoken language dialect code. |

---

## 8. Deferred Subsystems & Future Integration

> [!IMPORTANT]
> **Explicit Architectural Boundaries**:
> - **Wake Word Detection ("Hey ASTRA"):** The local wake word engine is preserved in `src/voice/wake/` and its interfaces remain functional, but full continuous wake word integration is **intentionally deferred to Phase V2-05**.
> - **Full Barge-in Playback Interruption:** The foundational interruption hooks (`stop()`, `is_speaking()`, `pause_stream()`) have been implemented in this phase, but continuous real-time barge-in cancellation during active speech playback is **intentionally deferred to Phase V2-06**.
