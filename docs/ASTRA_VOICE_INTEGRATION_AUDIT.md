# ASTRA Voice Subsystem — Natural Voice Conversation Integration Audit

## 1. Executive Summary

This document presents a comprehensive audit of ASTRA's voice conversation architecture, spanning audio hardware capture, voice activity detection (VAD), speech segmentation, speech-to-text (STT), cognitive agent orchestration, Large Language Model (LLM) providers (Gemini and Ollama), text-to-speech (TTS), audio output streaming, real-time barge-in speech interruption, FastAPI/WebSocket communication, and React frontend state synchronization.

The objective of this phase is to deliver reliable, natural spoken conversation end-to-end:
```
User speaks
  ↓
Microphone Capture (16kHz 16-bit mono)
  ↓
Speech Endpoint Detection (VAD + SpeechSegmenter)
  ↓
STT Transcription (SpeechRecognition / Google STT)
  ↓
ASTRA Agent (Cognitive Orchestrator & Context Manager)
  ↓
Configured LLM Provider (Ollama / Gemini)
  ↓
Final Response Text
  ↓
TTS Synthesis (ElevenLabs / Pyttsx3 SAPI5)
  ↓
Audio Playback (sounddevice linear PCM)
  ↓
User Can Speak Again (Continuous Loop / Wake Word / Tap-to-Talk)
```

---

## 2. Current Voice Architecture

ASTRA's voice system is organized as a modular, event-driven subsystem centered in `src/voice/`:

```
                                  ┌───────────────────────────────┐
                                  │         VoiceManager          │
                                  │   (High-level Facade/Life)   │
                                  └──────────────┬────────────────┘
                                                 │
            ┌─────────────────────┬──────────────┴───────────────┬─────────────────────┐
            │                     │                              │                     │
  ┌─────────▼────────┐  ┌─────────▼────────┐          ┌──────────▼─────────┐ ┌─────────▼────────┐
  │MicrophoneManager │  │ SpeechSegmenter  │          │   VoiceSession     │ │ WakeWordListener │
  │ (sounddevice mic)│  │ (Energy RMS+VAD) │          │  (State Machine)   │ │  ("Hey Astra")   │
  └─────────┬────────┘  └─────────┬────────┘          └──────────┬─────────┘ └──────────────────┘
            │                     │                              │
            └──────────────┬──────┴──────────────────────────────┘
                           │
       ┌───────────────────┼───────────────────┐
       │                   │                   │
┌──────▼──────┐     ┌──────▼──────┐     ┌──────▼──────┐
│ STTProvider │     │ AstraAgent  │     │ TTSProvider │
│ (Google STT)│     │(LLM Client) │     │(ElevenLabs) │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                      ┌────────▼─────────┐
                                      │BargeInCoordinator│
                                      │ (Real-Time Halt) │
                                      └──────────────────┘
```

### 2.1 Core Components
1. **`VoiceManager` (`src/voice/manager.py`)**:
   Top-level facade that coordinates `MicrophoneManager`, `VoiceActivityDetector`, `SpeechToTextProvider`, `TextToSpeechProvider`, `VoiceSession`, `WakeWordDetector`/`WakeWordListener`, and subsystem health reporting via `HealthManager`.
2. **`VoiceSession` (`src/voice/session.py`)**:
   Finite state machine managing turn progression across `VoiceState` enums:
   `IDLE` → `LISTENING` → `SPEECH_DETECTED` → `CAPTURING` → `PROCESSING` → `SPEAKING` → `IDLE` (or `BARGE_IN_DETECTED` → `INTERRUPTED`).
3. **`MicrophoneManager` (`src/voice/microphone.py`)**:
   Continuous non-blocking audio capture at 16kHz mono 16-bit PCM (480 samples / 30ms frames) using `sounddevice.InputStream`. Features hardware device enumeration, diagnostic telemetry, and overflow tolerance.
4. **`SpeechSegmenter` (`src/voice/segmenter.py`)**:
   Tracks pre-roll frames (~500ms), speech onset energy gating, sustained utterance collection, post-roll silence timeout (~1.0s), and yields isolated `AudioSegment` instances.
5. **`BargeInCoordinator` & `BargeInDetector` (`src/voice/barge_in.py`)**:
   Continuously reads microphone frames while TTS audio is playing. If speech is detected above `barge_in_energy_threshold` for `barge_in_min_speech_duration` (~250ms), halts TTS playback instantly (<50ms) and buffers onset phonemes for the next turn.
6. **`WakeWordListener` (`src/voice/wake/engine.py`)**:
   Hands-free background listener detecting "Hey Astra" when in `IDLE`/`SLEEPING` state, triggering automatic voice turn progression without touching the keyboard or mouse.

---

## 3. Existing STT and TTS Providers

### 3.1 Speech-To-Text (STT) Providers (`src/voice/stt.py`)
- **`SpeechRecognitionSTTProvider`**:
  Uses `speech_recognition` (Google Speech Recognition API). Converts 16kHz PCM audio buffers to WAV in-memory and returns normalized transcripts. Rejects silence/low-energy frames (<100 RMS) locally before network transmission.
- **`MockSTTProvider`**:
  Configurable mock for deterministic unit and integration tests.
- **`STTProviderFactory`**:
  Resolves `"speech_recognition"`, `"google"`, or `"mock"` without silent fallback.

### 3.2 Text-To-Speech (TTS) Providers (`src/voice/tts.py`, `src/voice/elevenlabs_provider.py`)
- **`ElevenLabsTTSProvider`**:
  Production cloud neural voice provider. Queries `https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=pcm_16000`. Streams 16kHz linear PCM bytes directly to `sounddevice.play()`. Sentence chunking ensures fast time-to-first-phoneme. Supports instant barge-in interruption via `stop()`.
- **`Pyttsx3TTSProvider`**:
  Offline Windows SAPI5 TTS fallback running on a dedicated worker thread with COM initialization (`ole32.CoInitialize`).
- **`MockTTSProvider`**:
  Mock provider storing spoken history for testing.
- **`TTSProviderFactory`**:
  Resolves `"elevenlabs"`, `"pyttsx3"`, or `"mock"`.

---

## 4. Existing Microphone Capture Flow

1. `MicrophoneManager.start_stream()` initializes a non-blocking `sd.InputStream` at 16,000 Hz, 1 channel, 16-bit integer format (`int16`), with blocksize of 480 frames (30ms per chunk).
2. The sounddevice audio callback appends each raw chunk into a thread-safe frame queue (`queue.Queue[AudioFrame]`).
3. If an input overflow occurs (`status.input_overflow`), a warning is logged and the diagnostics counter is incremented without crashing the stream.
4. Consumers (`SpeechSegmenter`, `BargeInDetector`, `WakeWordListener`) read audio frames via `read_frame(timeout=0.1)`.

---

## 5. Existing Agent-to-LLM Flow

1. When a clean transcript is produced by STT, `VoiceSession.listen_and_process()` invokes `AstraAgent.process_command(transcript)`.
2. Inside `AstraAgent`:
   - Publishes `AstraEventType.AGENT_STARTED`.
   - Records user message in `ContextManager`.
   - Queries `LLMClient.generate_decision()` using configured provider (`GeminiProvider` or `OllamaProvider`).
   - If Ollama is configured (`LLM_PROVIDER=ollama`):
     - Sends structured JSON payload to `OLLAMA_BASE_URL/api/chat` (e.g. `https://ollama.com/api/chat` with model `gemma4:31b` or local Ollama daemon).
     - Authorization header `Bearer $OLLAMA_API_KEY` is injected securely without leaking in logs or exceptions.
   - If Gemini is configured (`LLM_PROVIDER=gemini`):
     - Uses Google GenAI SDK with structured function calling.
   - Executes tools (filesystem, system, applications, web, automation) via `CapabilityRegistry` / `ToolRegistry`.
   - Records turn result in `ContextManager`.
   - Publishes `AstraEventType.AGENT_COMPLETED` with final response text.
3. The response text is sanitized via `sanitize_text_for_speech()`:
   - Strips Markdown formatting, code fences, URLs, and table artifacts.
   - Redacts any sensitive keys or tokens via `SecretRedactionFilter`.
4. Spoken aloud via `VoiceSession.tts.speak(clean_speech_text, block=False)` while `BargeInCoordinator` monitors for user speech.

---

## 6. Existing API, WebSocket & UI Communication

ASTRA features a dual frontend runtime:
- **Primary Shell**: `AstraWebWindow` (`src/ui/web_shell.py`), a PySide6 QtWebEngine shell hosting the React Vite UI (`Astra voice UI/dist`) at `http://127.0.0.1:{bound_port}`.
- **CLI Fallback**: Interactive terminal CLI (`src/interfaces/cli.py`).

### React Frontend (`Astra voice UI/src/context/AppContext.jsx`)
- State machine in UI: `assistantState` (`idle` | `listening` | `thinking` | `speaking` | `interrupted`).
- Controls 3D `WebGLOrb`:
  - `0`: Idle (calm pulse)
  - `1`: Listening (faster rotation, reactive waveform)
  - `2`: Thinking (amber pulse, shifting shader tone)
  - `3`: Speaking (warm glowing center, audio-reactive bounce)
- Trigger methods:
  - `startVoiceInput()`: Calls `POST /api/v1/voice/listen`.
  - `stopVoiceInput()`: Calls `POST /api/v1/voice/stop`.
  - `speakText(text)`: Calls `POST /api/v1/voice/speak`.
- WebSocket listener:
  - Listens to `VOICE_STATE_CHANGED`, `BRAIN_STARTED`, `BRAIN_COMPLETED`, `HEALTH_CHANGED`, `ERROR_OCCURRED`.

---

## 7. Audit Findings: Gaps & Needed Fixes

| # | Subsystem / Area | Current State & Root Cause | Impact | Required Fix |
|---|---|---|---|---|
| **1** | **`UIEventAdapter` Async Event Loop** | `UIEventAdapter` in `src/core/events/adapters.py` initialized before uvicorn server thread starts. `self.loop` is `None`. From worker threads (voice, wake-word, agent), `asyncio.get_running_loop()` is `None`. | Events emitted on `EventBus` are dropped with "No active asyncio event loop available for UI broadcast." UI receives zero real-time voice updates from background threads. | Capture running asyncio event loop during FastAPI startup / lifespan and store on `UIEventAdapter` and `ws_manager`. |
| **2** | **Voice State Event Translation** | `VoiceSession` publishes `VOICE_LISTENING_STARTED`, `VOICE_SPEAKING_STARTED`, `VOICE_INTERRUPTED`, etc. `UIEventAdapter` broadcasts those literal event strings, but `AppContext.jsx` only listens for `VOICE_STATE_CHANGED` with `state: "listening"\|"thinking"\|"speaking"\|"interrupted"\|"idle"`. | The React WebGL orb and status pill do not update when voice transitions occur in background turns. | In `UIEventAdapter` (or `VoiceSession`), map voice events to `VOICE_STATE_CHANGED` envelopes with normalized state strings. |
| **3** | **Spoken Transcript Visibility in Chat** | In typed commands (`/api/v1/command`), `server.py` broadcasts `BRAIN_STARTED` (`input=text`) and `BRAIN_COMPLETED` (`response=text`). In voice commands (`/api/v1/voice/listen` or wake-word), `VoiceSession` calls `agent.process_command(transcript)`, but does not broadcast `BRAIN_STARTED` or `BRAIN_COMPLETED` with legacy fields expected by `AppContext`. | Spoken voice conversations never appear in the React chat UI history (`AppContext.messages`). The user speaks and hears ASTRA, but the transcript is missing on screen. | Emit `BRAIN_STARTED` and `BRAIN_COMPLETED` WebSocket envelopes when voice turns execute, carrying `input` and `response` fields so the UI displays the turn. |
| **4** | **`/api/v1/voice/listen` State Blocking** | `/api/v1/voice/listen` broadcasts `VOICE_STATE_CHANGED (listening)`, runs `listen_and_process` synchronously on thread pool, then broadcasts `VOICE_STATE_CHANGED (idle)`. | UI stays frozen in "LISTENING" state during STT transcription, LLM reasoning, and TTS speaking. | Rely on real-time event-driven state transitions broadcasted by `VoiceSession` via `EventBus` and `UIEventAdapter`. |
| **5** | **Barge-In Interruption Coordination** | When user clicks "Stop" button in UI, `POST /api/v1/voice/stop` calls `voice_manager.stop_speaking()`. If `monitor_while_speaking` is active, it halts TTS immediately. However, when user speaks vocal stop command ("stop", "cancel"), `session.py` catches it, but the state wasn't cleanly broadcasted as `interrupted` to the UI before returning to `idle`. | UI does not show momentary visual indicator of interruption before resetting. | Emit explicit `VOICE_STATE_CHANGED (interrupted)` event upon barge-in and stop triggers. |
| **6** | **Credential Protection in Spoken Output** | If agent returns a response containing API keys, URLs with tokens, or JSON errors, raw keys could potentially be spoken aloud or logged. | Severe credential exposure risk. | `sanitize_text_for_speech()` uses `SecretRedactionFilter.redact()` to ensure tokens are replaced with "[REDACTED]" and never vocalized. Verified. |

---

## 8. Files That Need Changes

1. **`src/core/events/adapters.py`**:
   - Add loop synchronization method `set_loop(loop)` to `UIEventAdapter`.
   - Add translation from voice domain events (`VOICE_LISTENING_STARTED`, `VOICE_CAPTURING_STARTED`, `VOICE_TRANSCRIBING`, `VOICE_SPEAKING_STARTED`, `VOICE_INTERRUPTED`, `VOICE_SESSION_ENDED`, `AGENT_STARTED`, `AGENT_COMPLETED`) to `VOICE_STATE_CHANGED`, `BRAIN_STARTED`, and `BRAIN_COMPLETED` WebSocket events.
2. **`src/api/server.py`**:
   - Register FastAPI startup lifespan handler to bind the running asyncio event loop to `app.state.ui_adapter` and `ws_manager`.
   - Refactor `/api/v1/voice/listen` to avoid overriding real-time state machine transitions.
3. **`src/voice/session.py`**:
   - Ensure clean state emission (`SPEECH_DETECTED`, `CAPTURING`, `PROCESSING`/`THINKING`, `SPEAKING`, `INTERRUPTED`, `IDLE`) with appropriate EventBus types.
   - Publish `AGENT_STARTED` and `AGENT_COMPLETED` with transcript and response details so UI synchronizes chat history automatically.
4. **`tests/test_natural_voice.py`**:
   - Create comprehensive unit and integration tests verifying end-to-end spoken turn flow, state transitions, barge-in stop, WebSocket event emission, error handling, and credential redaction.

---

## 9. Minimal Implementation Plan

1. **Step 1: Event Loop Binding in UIEventAdapter & FastAPI**:
   Ensure `UIEventAdapter` always holds the active event loop of the FastAPI server, allowing thread-safe cross-thread event dispatching from any worker thread.
2. **Step 2: Unified Voice State & Chat Synchronization**:
   Ensure voice state changes (`listening`, `thinking`, `speaking`, `interrupted`, `idle`) and turn contents (`transcript`, `response`) are broadcast to WebSocket clients so React UI (`AppContext.jsx` and `WebGLOrb.jsx`) reflects the actual voice pipeline in real-time.
3. **Step 3: Verification of Ollama & Gemini LLM Pipeline with Voice**:
   Confirm that when `LLM_PROVIDER=ollama` or `LLM_PROVIDER=gemini`, the agent processes voice transcripts cleanly and delivers responses to TTS.
4. **Step 4: Comprehensive Test Suite**:
   Write `tests/test_natural_voice.py` covering all state transitions, barge-in interruption, STT failures, empty input, and secret scrubbing.
5. **Step 5: Documentation**:
   Create `docs/ASTRA_NATURAL_VOICE.md` summarizing the operational voice architecture.
