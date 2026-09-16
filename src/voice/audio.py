"""
Audio Stream Utilities.
Provides PCM buffer analysis, RMS volume calculation, WAV header generation,
audio duration calculation, synthetic signal generation for testing, and transcript normalization.
"""

import io
import math
import struct
import wave


def calculate_rms(pcm_data: bytes, sample_width: int = 2) -> float:
    """Calculate Root Mean Square (RMS) energy level of 16-bit PCM audio bytes."""
    if not pcm_data:
        return 0.0

    count = len(pcm_data) // sample_width
    if count == 0:
        return 0.0

    format_str = f"<{count}h" if sample_width == 2 else f"<{count}b"
    try:
        samples = struct.unpack(format_str, pcm_data[: count * sample_width])
        sum_squares = sum(s * s for s in samples)
        rms = math.sqrt(sum_squares / count)
        return float(rms)
    except struct.error:
        return 0.0


def pcm_duration_seconds(
    pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2
) -> float:
    """Compute duration in seconds for a given PCM audio buffer."""
    if not pcm_data or sample_rate <= 0 or channels <= 0 or sample_width <= 0:
        return 0.0
    bytes_per_second = sample_rate * channels * sample_width
    return len(pcm_data) / float(bytes_per_second)


def generate_silence(
    duration_s: float, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2
) -> bytes:
    """Generate raw PCM silence bytes for a specified duration."""
    total_samples = int(duration_s * sample_rate * channels)
    return b"\x00" * (total_samples * sample_width)


def generate_tone(
    duration_s: float, frequency: float = 440.0, sample_rate: int = 16000, amplitude: float = 10000.0
) -> bytes:
    """Generate a 16-bit mono sine wave PCM buffer for testing VAD and audio processing."""
    total_samples = int(duration_s * sample_rate)
    pcm_out = bytearray()
    for i in range(total_samples):
        val = int(amplitude * math.sin(2 * math.pi * frequency * i / sample_rate))
        val = max(-32768, min(32767, val))
        pcm_out.extend(struct.pack("<h", val))
    return bytes(pcm_out)


def convert_to_wav(
    pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2
) -> bytes:
    """Wrap raw 16-bit PCM bytes into a standard in-memory WAV byte stream."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buffer.getvalue()


def normalize_transcript(text: str) -> str:
    """Clean and normalize transcript text without altering fundamental meaning."""
    if not text:
        return ""

    # Strip excess whitespace and normalize casing
    cleaned = " ".join(text.strip().split())

    # Remove leading punctuation artifacts if any
    cleaned = cleaned.lstrip(".?,!;: ")
    return cleaned
