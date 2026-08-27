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

        logger.info(f"Creating OCRProvider for '{provider_name}'")
        return MockOCRProvider()
