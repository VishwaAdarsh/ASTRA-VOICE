"""
Audio Stream Utilities.
Provides PCM buffer analysis, RMS volume calculation, WAV header generation, and transcript normalization.
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
