"""
Vision Provider Factory.
"""

from src.core.config import Config
from src.core.logger import get_logger
from src.vision.models.mock_provider import MockVisionProvider
from src.vision.models.provider import VisionProvider

logger = get_logger()


class VisionProviderFactory:
    """Factory for creating VisionProvider instances."""

    @staticmethod
    def create(config: Config | None = None) -> VisionProvider:
        cfg = config or Config()
        provider_name = cfg.vision_provider.strip().lower()

        logger.info(f"Creating VisionProvider for '{provider_name}'")
        return MockVisionProvider()
