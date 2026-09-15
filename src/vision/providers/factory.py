"""
Vision Provider Factory.
"""

from src.core.config import Config
from src.core.logger import get_logger
from src.vision.providers.mock_provider import MockVisionProvider
from src.vision.providers.provider import VisionProvider

logger = get_logger()


class VisionProviderFactory:
    """Factory for creating VisionProvider instances."""

    @staticmethod
    def create(config: Config | None = None) -> VisionProvider:
        cfg = config or Config()
        provider_name = cfg.vision_provider.strip().lower()

        if provider_name in ("mock", "test", "default", ""):
            return MockVisionProvider()
        raise NotImplementedError(
            f"Vision provider '{provider_name}' is not yet registered. "
            "Real Vision integration is scheduled for Phase V2-02. "
            "Set VISION_PROVIDER=mock for testing."
        )

