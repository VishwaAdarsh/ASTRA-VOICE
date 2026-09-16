"""
OpenWakeWord Local Neural Wake-Word Detector.
Uses local ONNX runtime neural models to detect 'Hey ASTRA' or custom wake phrases
offline with zero cloud latency and zero remote data transmission.
"""

from pathlib import Path
import numpy as np

from src.core.logger import get_logger
from src.voice.errors import WakeModelMissingError, WakeDetectorInitError
from src.voice.models import AudioFrame, WakeDetectionResult
from src.voice.wake.detector import WakeWordDetector

logger = get_logger()


class OpenWakeWordDetector(WakeWordDetector):
    """Local neural wake-word detector using openWakeWord ONNX models."""

    def __init__(
        self,
        wake_phrase: str = "hey astra",
        model_path: str = "",
        threshold: float = 0.6,
        sample_rate: int = 16000,
    ):
        super().__init__(wake_phrase=wake_phrase, threshold=threshold, sample_rate=sample_rate)
        self.engine_name = "openwakeword"
        self.model_path = model_path
        self._model = None
        self._target_key = self.wake_phrase.replace(" ", "_")

    def initialize(self) -> bool:
        """Initialize openWakeWord ONNX model instance."""
        try:
            import openwakeword
            from openwakeword.model import Model

            # If an explicit model path is provided, ensure it exists
            custom_models = []
            if self.model_path:
                p = Path(self.model_path)
                if not p.exists():
                    logger.warning(f"[WAKE] Specified openWakeWord model not found at '{self.model_path}'")
                    raise WakeModelMissingError(f"Wake word model not found: {self.model_path}")
                custom_models.append(str(p))

            # Instantiate openWakeWord Model
            if custom_models:
                self._model = Model(wakeword_models=custom_models)
            else:
                # Default built-in models (e.g. 'alexa', 'hey_jarvis' as baseline fallback)
                self._model = Model()

            self._is_ready = True
            logger.info(f"[WAKE] OpenWakeWordDetector initialized successfully (threshold={self.threshold})")
            return True

        except WakeModelMissingError:
            self._is_ready = False
            raise
        except Exception as e:
            self._is_ready = False
            logger.error(f"[WAKE] Failed to initialize openWakeWord: {e}")
            raise WakeDetectorInitError(f"openWakeWord initialization failed: {e}")

    def reset(self) -> None:
        """Reset internal prediction buffers."""
        if self._model is not None:
            try:
                self._model.reset()
            except Exception:
                pass

    def process_audio(self, frame: AudioFrame) -> WakeDetectionResult:
        """Feed 16-bit PCM chunk to openWakeWord model and check predictions."""
        if not self._is_ready or self._model is None or not frame.data:
            return WakeDetectionResult(detected=False, keyword=self.wake_phrase)

        try:
            # openWakeWord expects 16-bit PCM array or int16 numpy array
            audio_samples = np.frombuffer(frame.data, dtype=np.int16)
            prediction = self._model.predict(audio_samples)

            # Check if any loaded model crossed threshold
            max_conf = 0.0
            detected = False
            detected_key = self.wake_phrase

            for key, score in prediction.items():
                if score > max_conf:
                    max_conf = float(score)
                if score >= self.threshold:
                    detected = True
                    detected_key = key
                    break

            if detected:
                logger.info(f"[WAKE] openWakeWord triggered for '{detected_key}' with confidence {max_conf:.2f}")
                self.reset()
                return WakeDetectionResult(
                    detected=True,
                    confidence=max_conf,
                    keyword=detected_key,
                    metadata={"scores": prediction},
                )

            return WakeDetectionResult(
                detected=False,
                confidence=max_conf,
                keyword=self.wake_phrase,
                metadata={"scores": prediction},
            )

        except Exception as e:
            logger.debug(f"[WAKE] openWakeWord inference error: {e}")
            return WakeDetectionResult(detected=False, keyword=self.wake_phrase)

    def close(self) -> None:
        self.stop()
        self._model = None
        self._is_ready = False
