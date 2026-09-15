# ADR-003: Provider Separation & Prohibition of Silent Mock Fallbacks

**Status:** Accepted  
**Date:** 2026-09-16  
**Phase:** V2-01  

---

## Context
ASTRA uses provider abstractions across multiple subsystems: LLM, Speech-to-Text (STT), Text-to-Speech (TTS), Web Search, Vision, and OCR. Each subsystem provides both real production implementations (e.g. Gemini, SpeechRecognition, Pyttsx3 SAPI5, DuckDuckGo) and deterministic mock implementations for testing.

Previously, several provider factories (such as `SearchProviderFactory`) silently fell back to returning mock providers if an unrecognized provider string was passed. Silent mock degradation conceals misconfiguration and leads to unpredictable behavior where production users believe they are using real external services when they are actually interacting with hardcoded mocks.

---

## Decision
1. **Maintain strict structural separation between Real Providers and Mock Providers.**
2. **Eliminate silent fallback to mock implementations.**
   - All provider factories (`LLMProviderFactory`, `STTProviderFactory`, `TTSProviderFactory`, `SearchProviderFactory`, `VisionProviderFactory`, `OCRProviderFactory`) must require explicit provider configuration.
   - If a provider is unrecognized or misconfigured, the factory must raise a descriptive exception (`ValueError`, `AstraError`, or `NotImplementedError`) rather than silently returning a mock.
   - Mock providers are only instantiated when the configuration explicitly requests `"mock"` or `"test"`.
3. Retain all mock implementations for offline development and deterministic unit testing.

---

## Consequences
- **Positive:**
  - Clear observability: errors in provider configuration or API keys fail fast and conspicuously.
  - Test predictability: test suites explicitly configure `"mock"`, while production environments never accidentally run in mock mode.
- **Negative:**
  - Misconfigured environments will raise startup/execution errors rather than silently limping along with dummy responses.
