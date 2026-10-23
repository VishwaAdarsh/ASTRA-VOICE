# ASTRA Natural Voice Conversation Architecture & Integration

## 1. Overview & Architecture

ASTRA features an end-to-end, production-grade natural voice conversation pipeline. It connects continuous microphone capture, Voice Activity Detection (VAD), Speech-to-Text (STT), cognitive Agent execution with real LLM providers (Ollama or Gemini), Text-to-Speech (TTS), audio output playback, real-time barge-in interruption, and bidirectional WebSocket state synchronization with the desktop React Stitch UI.

```
+-----------------------------------------------------------------------------------+
|                                 USER SPEAKS                                       |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                        1. Audio Capture (MicrophoneManager)                       |
|   - 16kHz, 16-bit linear PCM, mono                                                |
|   - Non-blocking sounddevice.InputStream callback (30ms chunks / 480 samples)     |
|   - Hardware diagnostics & input overflow tolerance                               |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                   2. Voice Activity Detection & Segmentation                      |
|   - SpeechSegmenter (pre-roll ~500ms, energy RMS gating)                           |
|   - Speech onset detection -> emits VOICE_CAPTURING_STARTED                       |
|   - Sustained speech accumulation & silence timeout (~1.0s)                       |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                       3. Speech-to-Text (STT Transcription)                       |
|   - SpeechRecognitionSTTProvider (Google STT) / MockSTTProvider                   |
|   - Local low-energy silence filtering (RMS < 100 rejected locally)               |
|   - Emits VOICE_TRANSCRIBING -> UI enters 'thinking' state                        |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                 4. ASTRA Agent & LLM Orchestrator (AstraAgent)                    |
|   - ContextManager records user utterance into conversation history               |
|   - LLMClient queries configured provider:                                        |
|       * OllamaProvider (e.g. gemma4:31b via https://ollama.com/api/chat)         |
|       * GeminiProvider (gemini-3.6-flash via Google GenAI SDK)                    |
|   - Multi-step tool reasoning & capability execution (filesystem, system, web)    |
|   - Emits BRAIN_STARTED and BRAIN_COMPLETED with source='voice'                   |
|   - UI displays user prompt & assistant response in chat transcript               |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                       5. Response Text Sanitization & TTS                         |
|   - sanitize_text_for_speech():                                                   |
|       * Strips Markdown formatting, code fences, and URLs                         |
|       * Redacts sensitive tokens/keys via SecretRedactionFilter                   |
|   - TTSProviderFactory resolves:                                                  |
|       * ElevenLabsTTSProvider (16kHz PCM streaming to sounddevice)                |
|       * Pyttsx3TTSProvider (Offline SAPI5 on dedicated worker thread)             |
|   - Emits VOICE_SPEAKING_STARTED -> UI WebGLOrb glows warm and reacts             |
+-----------------------------------------------------------------------------------+
                                          |
                         +----------------+----------------+
                         |                                 |
                         v                                 v
+-----------------------------------+     +-----------------------------------+
|   6A. Barge-In Interruption       |     |      6B. Normal Completion        |
| - BargeInCoordinator checks mic   |     | - Speech finishes naturally       |
| - User speaks or says "stop"      |     | - Emits VOICE_SESSION_ENDED       |
| - TTS halted immediately (<50ms)  |     | - UI returns to 'idle'            |
| - Emits VOICE_INTERRUPTED         |     | - User can speak again immediately|
| - UI shows 'interrupted' state    |     +-----------------------------------+
+-----------------------------------+
```

---

## 2. Voice State Machine & Lifecycle Transitions

ASTRA enforces explicit state transitions managed by `VoiceSession` in `src/voice/session.py`:

```
               [IDLE]
                 │
                 │ (Wake word "Hey Astra" or UI mic button)
                 ▼
            [LISTENING] ────── (Timeout without speech) ──────► [IDLE]
                 │
                 │ (Speech start detected by VAD)
                 ▼
            [CAPTURING]
                 │
                 │ (Speech end / silence detected)
                 ▼
            [PROCESSING] (STT + Agent LLM Reasoning)
                 │
                 │ (Agent response generated)
                 ▼
             [SPEAKING] ◄─────────────────────────────────┐
                 │                                        │
        ┌────────┴────────┐                               │
        │                 │ (User barge-in or stop)       │
        ▼                 ▼                               │
     [IDLE]         [INTERRUPTED]                         │
 (Speech completed)       │                               │
                          │ (Follow-up utterance detected)│
                          └───────────────────────────────┘
```

### State Definitions & UI Mapping:
| VoiceState | UI `assistantState` | WebGLOrb Uniform | Visual Feedback |
|---|---|---|---|
| `IDLE` | `idle` | `0.0` | Calm purple breathing orb; "Tap orb or say 'Hey Astra'" |
| `LISTENING` / `CAPTURING` | `listening` | `1.0` | Red active pulse; dynamic audio waveform; "Listening..." |
| `PROCESSING` | `thinking` | `2.0` | Amber rotating highlights; "Processing: '[transcript]'" |
| `SPEAKING` | `speaking` | `3.0` | Warm golden glowing center; bouncing audio amplitude; "Speaking..." |
| `INTERRUPTED` | `interrupted` | `0.0` | Amber flash pill; "Interrupted..."; immediate audio cutoff |
| `ERROR` | `error` | `0.0` | Red pill indicator; spoken recovery notice; return to idle |

---

## 3. Real-Time WebSocket Synchronization

The FastAPI backend server communicates with the React frontend using a standardized, bounded envelope via `/api/v1/ws`.

### Thread-Safe Event Loop Bridging (`UIEventAdapter`)
Because speech capture and background wake-word listening operate on dedicated OS worker threads, `UIEventAdapter` in `src/core/events/adapters.py` binds to FastAPI's running event loop during application startup (`@asynccontextmanager lifespan`). It safely dispatches events across threads using `asyncio.run_coroutine_threadsafe()`.

### Key WebSocket Messages Broadcast to the UI:
1. **`VOICE_STATE_CHANGED`**:
   ```json
   {
     "type": "VOICE_STATE_CHANGED",
     "state": "listening" | "thinking" | "speaking" | "interrupted" | "idle",
     "source": "voice",
     "timestamp": "2026-10-23T18:20:00Z"
   }
   ```
2. **`BRAIN_STARTED`**:
   ```json
   {
     "type": "BRAIN_STARTED",
     "input": "what time is it",
     "source": "voice",
     "request_id": "voice-1792759924550"
   }
   ```
   *UI action: Displays user transcript in the chat view and sets the thinking prompt indicator.*
3. **`BRAIN_COMPLETED`**:
   ```json
   {
     "type": "BRAIN_COMPLETED",
     "response": "The current time is 06:20 PM.",
     "source": "voice",
     "status": "SUCCESS",
     "request_id": "voice-1792759924550"
   }
   ```
   *UI action: Appends the assistant's answer to the conversation messages without forcing state to idle prematurely while speech is playing.*

---

## 4. Voice Interruption & Barge-In Detection

ASTRA provides real-time speech interruption through two coordinated paths:

### 4.1 Vocal Barge-In (`BargeInCoordinator` & `BargeInDetector`)
- Continuous microphone monitoring continues concurrently while TTS audio plays out of the soundcard.
- A 200ms initial grace period prevents speaker audio ramp-up from falsely triggering interruption.
- When user speech exceeds `barge_in_energy_threshold` (default 650 RMS) for longer than `barge_in_min_speech_duration` (default 250ms):
  1. `ElevenLabsTTSProvider.stop()` halts audio playback immediately (<50ms).
  2. Preserves buffered onset audio frames so the user's interruption words are not clipped.
  3. If user says a stop command ("stop", "cancel", "quiet", "be quiet", "shut up"), ASTRA halts and returns directly to `IDLE`.
  4. If user speaks a new command, ASTRA transitions to `LISTENING` and executes the new command.

### 4.2 Programmatic UI Interruption (`POST /api/v1/voice/stop`)
- When the user taps the active WebGL Orb or clicks "Stop" in the UI:
  1. `VoiceManager.stop_speaking()` signals `_cancel_requested`.
  2. Any active sounddevice playback is stopped immediately.
  3. Any active microphone listening or VAD segmentation loop unblocks instantly and returns to `IDLE`.
  4. State resets cleanly to `IDLE` with zero hanging threads.

---

## 5. LLM Provider Flexibility: Ollama & Gemini

ASTRA cleanly decouples cognitive reasoning from voice hardware:
- **Ollama Provider (`OllamaProvider`)**:
  When `LLM_PROVIDER=ollama` is set in `.env`:
  - Queries `https://ollama.com/api/chat` or local daemon (`OLLAMA_BASE_URL`).
  - Supports `gemma4:31b` or any configured model (`OLLAMA_MODEL`).
  - Passes structured tool schemas and returns structured decisions.
- **Gemini Provider (`GeminiProvider`)**:
  When `LLM_PROVIDER=gemini` is set in `.env`:
  - Queries Google Gemini API (`gemini-3.6-flash`).
  - Native function calling.

The voice pipeline behaves identically regardless of the active LLM provider.

---

## 6. Security & Secret Redaction

ASTRA enforces strict credential privacy:
1. **Never Spoken Aloud**: `sanitize_text_for_speech()` filters all response text through `SecretRedactionFilter.redact()`. Any API keys (`sk_...`, `AIza...`, `Bearer ...`) are replaced with `[REDACTED]` prior to speech synthesis.
2. **Never Logged or Broadcast**: The FastAPI WebSocket manager and logging filters redact tokens from all outgoing JSON payloads and log records.
3. **Environment-Only Configuration**: All keys (`TTS_API_KEY`, `OLLAMA_API_KEY`, `GEMINI_API_KEY`) are loaded via environment variables and never committed to source or tests.

---

## 7. Configuration Reference

```ini
# Voice Configuration
VOICE_ENABLED=true
VOICE_LANGUAGE=en-US
LISTEN_TIMEOUT=10.0
SILENCE_TIMEOUT=1.0

# Speech-to-Text (STT)
STT_PROVIDER=speech_recognition    # 'speech_recognition' or 'mock'

# Text-to-Speech (TTS)
TTS_PROVIDER=elevenlabs            # 'elevenlabs', 'pyttsx3', or 'mock'
TTS_API_KEY=<YOUR_API_KEY>
TTS_MODEL=eleven_turbo_v2_5
TTS_VOICE_ID=JBFqnCBsd6RMkjVDRZzb
TTS_BASE_URL=https://api.elevenlabs.io

# Hands-Free Wake Word
WAKE_WORD_ENABLED=true
WAKE_WORD_PHRASE=hey astra

# Voice Barge-In / Interruption
BARGE_IN_ENABLED=true
BARGE_IN_ENERGY_THRESHOLD=650.0
BARGE_IN_MIN_SPEECH_DURATION=0.25

# Cognitive LLM Provider
LLM_PROVIDER=gemini                # 'gemini', 'ollama', or 'mock'
GEMINI_API_KEY=<YOUR_API_KEY>
OLLAMA_API_KEY=<YOUR_API_KEY>
OLLAMA_MODEL=gemma4:31b
OLLAMA_BASE_URL=https://ollama.com
```

---

## 8. Verification & Test Suite

The natural voice subsystem is validated by automated tests in `tests/test_natural_voice.py` and the broader suite:

- `test_end_to_end_voice_turn_success`: Complete voice turn mic -> STT -> Agent -> TTS -> IDLE.
- `test_voice_state_transitions_to_event_bus`: Verified canonical `AstraEventType` emissions.
- `test_ui_event_adapter_broadcasts_voice_state_changed`: Verified UI state envelope translation.
- `test_spoken_command_bridges_brain_started_completed`: Verified user voice turns appear in chat.
- `test_voice_interruption_barge_in`: Verified instant TTS halt and transition to INTERRUPTED.
- `test_voice_stop_endpoint_cancels_active_session`: Verified instantaneous UI cancellation.
- `test_voice_turn_with_ollama_provider`: Verified full turn with Ollama LLM provider.
- `test_voice_empty_speech_returns_idle`: Verified graceful timeout and silence recovery.
- `test_voice_stt_error_recovery`: Verified speech error notification and safe recovery.
- `test_voice_turn_secret_scrubbing`: Verified credential scrubbing before vocalization.
