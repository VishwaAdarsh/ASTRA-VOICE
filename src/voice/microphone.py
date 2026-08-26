"""
Microphone Input Hardware Manager.
Handles input device discovery, device selection, stream capture, and error recovery.
"""

from typing import Any
import sounddevice as sd
from src.core.exceptions import AstraError
from src.core.logger import get_logger
from src.voice.models import AudioConfig, AudioDiagnostics

logger = get_logger()


class MicrophoneUnavailableError(AstraError):
    """Raised when no valid microphone device is detected or available."""

    pass


class MicrophoneManager:
    """Discovers, selects, and captures audio input from Windows microphone devices."""

    def __init__(self, audio_config: AudioConfig | None = None):
        self.config = audio_config or AudioConfig()
        self._stream: sd.InputStream | None = None
        self._is_capturing = False

    def list_microphones(self) -> list[dict[str, Any]]:
        """Discover available audio input devices on the machine."""
        devices = []
        try:
            device_list = sd.query_devices()
            for idx, dev in enumerate(device_list):
                if dev.get("max_input_channels", 0) > 0:
                    devices.append(
                        {
                            "index": idx,
                            "name": dev.get("name", f"Microphone {idx}"),
                            "channels": dev.get("max_input_channels", 1),
                            "sample_rate": int(dev.get("default_samplerate", 16000)),
                            "is_default": idx == sd.default.device[0],
                        }
                    )
        except Exception as e:
            logger.error(f"Failed to query microphone devices: {e}")
        return devices

    def get_diagnostics(self) -> AudioDiagnostics:
        """Get diagnostic information for current microphone setup."""

        mics = self.list_microphones()
        if not mics:
            return AudioDiagnostics(
                device_name="None",
                sample_rate=self.config.sample_rate,
                channels=self.config.channels,
                status="UNAVAILABLE",
                is_available=False,
            )

        selected = mics[0]
        if self.config.device_index is not None:
            for m in mics:
                if m["index"] == self.config.device_index:
                    selected = m
                    break

        return AudioDiagnostics(
            device_name=selected["name"],
            sample_rate=selected["sample_rate"],
            channels=selected["channels"],
            status="READY" if not self._is_capturing else "RECORDING",
            is_available=True,
        )

    def record_chunk(self, duration_seconds: float) -> bytes:
        """Capture a fixed duration chunk of 16-bit PCM audio bytes."""
        sample_rate = self.config.sample_rate
        channels = self.config.channels
        frames_to_record = int(duration_seconds * sample_rate)

        try:
            logger.info(f"Microphone recording for {duration_seconds:.1f}s at {sample_rate}Hz...")
            self._is_capturing = True

            # Record using sounddevice NumPy array recording
            recording = sd.rec(
                frames_to_record,
                samplerate=sample_rate,
                channels=channels,
                dtype="int16",
                device=self.config.device_index,
            )
            sd.wait()  # Wait until recording finishes
            self._is_capturing = False

            # Convert numpy array to raw bytes
            return recording.tobytes()

        except Exception as e:
            self._is_capturing = False
            logger.error(f"Microphone audio recording failed: {e}")
            raise MicrophoneUnavailableError(f"Microphone input failed: {e}")
