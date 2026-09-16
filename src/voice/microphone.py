"""
Microphone Input Hardware Manager.
Handles input device discovery, device selection, continuous audio stream capture,
bounded backpressure frame queuing, diagnostics, and graceful error recovery.
"""

import queue
import threading
import time
from typing import Any
import sounddevice as sd

from src.core.logger import get_logger
from src.voice.errors import AudioDeviceError, MicrophoneUnavailableError
from src.voice.models import AudioConfig, AudioDiagnostics, AudioFrame

logger = get_logger()


class MicrophoneManager:
    """Discovers, selects, and streams audio input continuously from microphone hardware."""

    def __init__(self, audio_config: AudioConfig | None = None):
        self.config = audio_config or AudioConfig()
        self._stream: sd.InputStream | None = None
        self._is_capturing = False
        self._is_paused = False
        self._lock = threading.Lock()

        # Bounded frame queue for continuous delivery with backpressure protection
        self._frame_queue: queue.Queue[AudioFrame] = queue.Queue(maxsize=100)
        self.active_sample_rate = self.config.sample_rate
        self._cached_default_device: dict[str, Any] | None = None

    @property
    def is_streaming(self) -> bool:
        """Check if continuous audio stream is currently active."""
        return self._stream is not None and self._is_capturing

    @property
    def is_paused(self) -> bool:
        """Check if audio frame consumption is paused."""
        return self._is_paused

    def get_default_device_info(self) -> dict[str, Any]:
        """Get device info for default or configured input device with caching."""
        if self._cached_default_device is not None:
            return self._cached_default_device

        try:
            dev_idx = (
                self.config.device_index
                if self.config.device_index is not None
                else sd.default.device[0]
            )
            if dev_idx is not None and dev_idx >= 0:
                dev_info = sd.query_devices(dev_idx)
                if isinstance(dev_info, list) and dev_info:
                    dev_info = dev_info[0]
                if isinstance(dev_info, dict):
                    res = {
                        "index": dev_idx,
                        "name": dev_info.get("name", "Default Microphone"),
                        "sample_rate": int(dev_info.get("default_samplerate", self.config.sample_rate)),
                        "channels": int(dev_info.get("max_input_channels", self.config.channels)),
                    }
                    self._cached_default_device = res
                    return res
        except Exception as e:
            logger.warning(f"Could not query default audio device: {e}")

        return {
            "index": None,
            "name": "Default Microphone",
            "sample_rate": self.config.sample_rate,
            "channels": self.config.channels,
        }

    def list_microphones(self) -> list[dict[str, Any]]:
        """Discover available audio input devices on the system."""
        devices = []
        try:
            device_list = sd.query_devices()
            default_in = sd.default.device[0] if sd.default.device else None
            for idx, dev in enumerate(device_list):
                if dev.get("max_input_channels", 0) > 0:
                    devices.append(
                        {
                            "index": idx,
                            "name": dev.get("name", f"Microphone {idx}"),
                            "channels": dev.get("max_input_channels", 1),
                            "sample_rate": int(dev.get("default_samplerate", 16000)),
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
            status="RECORDING" if self._is_capturing else "READY",
            is_available=True,
        )

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        """Stream callback invoked by sounddevice for each audio block."""
        if status:
            logger.warning(f"Microphone input stream warning: {status}")

        if self._is_paused or not self._is_capturing:
            return

        try:
            raw_bytes = indata.tobytes()
            frame = AudioFrame(
                data=raw_bytes,
                sample_rate=self.active_sample_rate,
                channels=self.config.channels,
                sample_width=self.config.sample_width,
                timestamp=time.time(),
            )
            # Push to bounded queue; if full, drop oldest to prevent memory growth
            try:
                self._frame_queue.put_nowait(frame)
            except queue.Full:
                try:
                    self._frame_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._frame_queue.put_nowait(frame)
                except queue.Full:
                    pass
        except Exception as e:
            logger.error(f"Error in microphone audio callback: {e}")

    def start_stream(self) -> None:
        """Open and start the continuous microphone capture stream."""
        with self._lock:
            if self._stream is not None and self._is_capturing:
                return

            dev_info = self.get_default_device_info()
            self.active_sample_rate = self.config.sample_rate

            try:
                chunk_size = self.config.chunk_size or int(self.active_sample_rate * 0.03)
                logger.info(
                    f"Opening continuous microphone stream on '{dev_info['name']}' "
                    f"({self.active_sample_rate}Hz, channels={self.config.channels}, chunk={chunk_size})..."
                )

                self._stream = sd.InputStream(
                    samplerate=self.active_sample_rate,
                    blocksize=chunk_size,
                    device=dev_info.get("index"),
                    channels=self.config.channels,
                    dtype="int16",
                    callback=self._audio_callback,
                )
                self._stream.start()
                self._is_capturing = True
                self._is_paused = False
                logger.info("Continuous microphone stream active.")
            except Exception as e:
                self._is_capturing = False
                self._stream = None
                logger.error(f"Failed to open microphone audio stream: {e}")
                raise MicrophoneUnavailableError(f"Could not open microphone stream: {e}")

    def stop_stream(self) -> None:
        """Stop and close the continuous microphone capture stream."""
        with self._lock:
            self._is_capturing = False
            self._is_paused = False

            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception as e:
                    logger.warning(f"Error closing microphone stream: {e}")
                finally:
                    self._stream = None

            # Drain leftover queued frames
            while not self._frame_queue.empty():
                try:
                    self._frame_queue.get_nowait()
                except queue.Empty:
                    break

            logger.info("Continuous microphone stream closed.")

    def pause_stream(self) -> None:
        """Temporarily pause audio frame delivery (e.g. during TTS playback)."""
        self._is_paused = True

    def resume_stream(self) -> None:
        """Resume audio frame delivery."""
        self._is_paused = False

    def read_frame(self, timeout: float = 0.1) -> AudioFrame | None:
        """Read a single audio frame from the continuous capture queue."""
        try:
            return self._frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def record_chunk(self, duration_seconds: float) -> tuple[bytes, int]:
        """
        Capture a fixed-duration chunk of 16-bit PCM audio bytes along with sample rate.
        Maintained for legacy callers and backward compatibility.
        """
        dev_info = self.get_default_device_info()
        sample_rate = dev_info["sample_rate"]
        self.active_sample_rate = sample_rate
        frames_to_record = int(duration_seconds * sample_rate)

        try:
            logger.info(
                f"Microphone recording on '{dev_info['name']}' for {duration_seconds:.1f}s at {sample_rate}Hz..."
            )
            self._is_capturing = True

            recording = sd.rec(
                frames_to_record,
                samplerate=sample_rate,
                channels=1,
                dtype="int16",
                device=dev_info["index"],
            )
            sd.wait()
            self._is_capturing = False

            pcm_data = recording.tobytes()
            logger.info(f"Microphone recorded {len(pcm_data)} PCM bytes ({sample_rate}Hz mono).")
            return pcm_data, sample_rate

        except Exception as e:
            self._is_capturing = False
            logger.error(f"Microphone audio recording failed: {e}")
            raise MicrophoneUnavailableError(f"Microphone input failed: {e}")
