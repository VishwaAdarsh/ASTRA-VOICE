"""
OCR Provider Factory.
"""

from src.core.config import Config
from src.core.logger import get_logger
from src.vision.ocr.mock_provider import MockOCRProvider
from src.vision.ocr.provider import OCRProvider

logger = get_logger()


class OCRProviderFactory:
    """Factory for creating OCRProvider instances."""

    @staticmethod
    def create(config: Config | None = None) -> OCRProvider:
        cfg = config or Config()
        provider_name = cfg.ocr_provider.strip().lower()

        if provider_name in ("mock", "test", "default", ""):
            return MockOCRProvider()
        raise NotImplementedError(
            f"OCR provider '{provider_name}' is not yet registered. "
            "Real OCR integration is scheduled for Phase V2-02. "
            "Set OCR_PROVIDER=mock for testing."
        )

