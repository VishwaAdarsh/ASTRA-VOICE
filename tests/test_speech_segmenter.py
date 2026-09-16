"""
Unit tests for SpeechSegmenter and VAD.
Tests speech start, speech continues, speech end, rolling pre-roll buffer,
maximum utterance limits, and minimum speech noise rejection.
"""

import time
from src.voice.audio import generate_silence, generate_tone
from src.voice.models import AudioConfig, AudioFrame, VADState
from src.voice.segmenter import SpeechSegmenter
from src.voice.vad import VoiceActivityDetector


def test_vad_speech_vs_silence():
    vad = VoiceActivityDetector(energy_threshold=200.0)
    
    silence = generate_silence(duration_s=0.1, sample_rate=16000)
    assert vad.is_speech(silence) is False
    assert vad.calculate_energy(silence) < 5.0

    tone = generate_tone(duration_s=0.1, frequency=440.0, sample_rate=16000, amplitude=5000.0)
    assert vad.is_speech(tone) is True
    assert vad.calculate_energy(tone) > 1000.0


def test_speech_segmenter_pre_roll_retention():
    """Verify that speech segment includes pre-roll frames recorded prior to speech detection."""
    cfg = AudioConfig(
        sample_rate=16000,
        frame_duration_ms=50,
        chunk_size=800,
        pre_roll_duration=0.2,  # 4 frames of pre-roll
        silence_timeout=0.2,
        minimum_speech_duration=0.1,
    )
    segmenter = SpeechSegmenter(audio_config=cfg)

    silence_data = generate_silence(0.05, sample_rate=16000)
    tone_data = generate_tone(0.05, frequency=440.0, sample_rate=16000, amplitude=5000.0)

    # 1. Feed 4 silence frames into pre-roll
    for i in range(4):
        state, segment = segmenter.process_frame(AudioFrame(data=silence_data, timestamp=time.time()))
        assert state == VADState.SILENCE
        assert segment is None

    # 2. Feed speech frame
    t_start = time.time()
    state, segment = segmenter.process_frame(AudioFrame(data=tone_data, timestamp=t_start))
    assert state == VADState.SPEECH_START
    assert segment is None
    assert segmenter.is_capturing is True

    # Speech buffer should contain 4 pre-roll frames + 1 speech frame = 5 frames
    assert len(segmenter._speech_frames) == 5


def test_speech_segmenter_end_on_silence():
    """Verify speech ends cleanly after trailing silence threshold is reached."""
    cfg = AudioConfig(
        sample_rate=16000,
        frame_duration_ms=50,
        chunk_size=800,
        pre_roll_duration=0.1,
        silence_timeout=0.15,
        minimum_speech_duration=0.1,
    )
    segmenter = SpeechSegmenter(audio_config=cfg)

    silence_data = generate_silence(0.05, sample_rate=16000)
    tone_data = generate_tone(0.05, frequency=440.0, sample_rate=16000, amplitude=5000.0)

    # Pre-roll silence
    segmenter.process_frame(AudioFrame(data=silence_data, timestamp=1.0))
    # Speech frames (3 frames = 0.15s of speech)
    segmenter.process_frame(AudioFrame(data=tone_data, timestamp=1.05))
    segmenter.process_frame(AudioFrame(data=tone_data, timestamp=1.10))
    segmenter.process_frame(AudioFrame(data=tone_data, timestamp=1.15))

    # Silence frames to trigger end
    state1, seg1 = segmenter.process_frame(AudioFrame(data=silence_data, timestamp=1.20))
    assert state1 == VADState.SPEECH_CONTINUES
    assert seg1 is None

    state2, seg2 = segmenter.process_frame(AudioFrame(data=silence_data, timestamp=1.25))
    assert state2 == VADState.SPEECH_CONTINUES
    assert seg2 is None

    # Third silence frame exceeds silence_timeout (0.15s)
    state3, seg3 = segmenter.process_frame(AudioFrame(data=silence_data, timestamp=1.36))
    assert state3 == VADState.SPEECH_END
    assert seg3 is not None
    assert seg3.duration_s > 0.15
    assert len(seg3.pcm_data) > 0


def test_speech_segmenter_maximum_utterance_cap():
    """Verify segmenter finalizes utterance when maximum duration is reached to protect against unbounded capture."""
    cfg = AudioConfig(
        sample_rate=16000,
        frame_duration_ms=100,
        chunk_size=1600,
        maximum_utterance_duration=0.5,  # 5 frames max
        silence_timeout=1.0,
        minimum_speech_duration=0.1,
    )
    segmenter = SpeechSegmenter(audio_config=cfg)
    tone_data = generate_tone(0.1, frequency=440.0, sample_rate=16000, amplitude=5000.0)

    # First speech frame
    segmenter.process_frame(AudioFrame(data=tone_data, timestamp=1.0))
    segmenter.process_frame(AudioFrame(data=tone_data, timestamp=1.1))
    segmenter.process_frame(AudioFrame(data=tone_data, timestamp=1.2))
    segmenter.process_frame(AudioFrame(data=tone_data, timestamp=1.3))

    # 5th frame reaches 0.5s limit
    state, seg = segmenter.process_frame(AudioFrame(data=tone_data, timestamp=1.4))
    assert state == VADState.SPEECH_END
    assert seg is not None
    assert seg.duration_s >= 0.5


def test_speech_segmenter_reject_short_noise():
    """Verify brief audio clicks (< minimum_speech_duration) are discarded as noise."""
    cfg = AudioConfig(
        sample_rate=16000,
        frame_duration_ms=50,
        chunk_size=800,
        minimum_speech_duration=0.2,  # Requires at least 0.2s of speech
        silence_timeout=0.1,
    )
    segmenter = SpeechSegmenter(audio_config=cfg)

    silence_data = generate_silence(0.05, sample_rate=16000)
    tone_data = generate_tone(0.05, frequency=440.0, sample_rate=16000, amplitude=5000.0)

    # 1 brief click frame (0.05s)
    segmenter.process_frame(AudioFrame(data=tone_data, timestamp=1.0))

    # Trailing silence
    segmenter.process_frame(AudioFrame(data=silence_data, timestamp=1.05))
    state, seg = segmenter.process_frame(AudioFrame(data=silence_data, timestamp=1.20))

    # Below minimum speech duration -> discarded as silence
    assert state == VADState.SILENCE
    assert seg is None
    assert segmenter.state == VADState.SILENCE
