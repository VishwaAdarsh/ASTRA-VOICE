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
        self.active_sample_rate = self.config.sample_rate

    def get_default_device_info(self) -> dict[str, Any]:
        """Get device info for default or configured input device."""
        try:
            dev_idx = self.config.device_index if self.config.device_index is not None else sd.default.device[0]
            if dev_idx is not None and dev_idx >= 0:
                dev_info = sd.query_devices(dev_idx)
                return {
                    "index": dev_idx,
                    "name": dev_info.get("name", "Default Microphone"),
                    "sample_rate": int(dev_info.get("default_samplerate", 44100)),
                    "channels": int(dev_info.get("max_input_channels", 1)),
                }
        except Exception as e:
            logger.warning(f"Could not query default audio device: {e}")

        return {
            "index": None,
            "name": "Default Microphone",
            "sample_rate": self.config.sample_rate,
            "channels": self.config.channels,
        }

    def list_microphones(self) -> list[dict[str, Any]]:
        """Discover available audio input devices on the machine."""
        devices = []
        try:
            device_list = sd.query_devices()
            default_in = sd.default.device[0]
            for idx, dev in enumerate(device_list):
                if dev.get("max_input_channels", 0) > 0:
                    devices.append(
                        {
                            "index": idx,
                            "name": dev.get("name", f"Microphone {idx}"),
                            "channels": dev.get("max_input_channels", 1),
                            "sample_rate": int(dev.get("default_samplerate", 44100)),
                            "is_default": idx == default_in,
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

        dev_info = self.get_default_device_info()
        return AudioDiagnostics(
            device_name=dev_info["name"],
            sample_rate=dev_info["sample_rate"],
            channels=dev_info["channels"],
            status="READY" if not self._is_capturing else "RECORDING",
            is_available=True,
        )

    def record_chunk(self, duration_seconds: float) -> tuple[bytes, int]:
        """Capture a fixed duration chunk of 16-bit PCM audio bytes along with sample rate."""
        dev_info = self.get_default_device_info()
        sample_rate = dev_info["sample_rate"]
        self.active_sample_rate = sample_rate
        frames_to_record = int(duration_seconds * sample_rate)

        try:
            logger.info(f"Microphone recording on '{dev_info['name']}' for {duration_seconds:.1f}s at {sample_rate}Hz...")
            self._is_capturing = True

            # Record mono 16-bit PCM audio array
            recording = sd.rec(
                frames_to_record,
                samplerate=sample_rate,
                channels=1,
                dtype="int16",
                device=dev_info["index"],
            )
            sd.wait()  # Wait until recording finishes
            self._is_capturing = False

            pcm_data = recording.tobytes()
            logger.info(f"Microphone recorded {len(pcm_data)} PCM bytes ({sample_rate}Hz mono).")
            return pcm_data, sample_rate

        except Exception as e:
            self._is_capturing = False
            logger.error(f"Microphone audio recording failed: {e}")
            raise MicrophoneUnavailableError(f"Microphone input failed: {e}")
