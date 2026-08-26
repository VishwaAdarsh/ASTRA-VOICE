"""
Search Provider Factory.
"""

from src.core.config import Config
from src.core.logger import get_logger
from src.web.search.duckduckgo import DuckDuckGoSearchProvider
from src.web.search.mock_provider import MockSearchProvider
from src.web.search.provider import SearchProvider

logger = get_logger()


class SearchProviderFactory:
    """Factory for creating SearchProvider instances."""

    @staticmethod
    def create(config: Config | None = None) -> SearchProvider:
        cfg = config or Config()
        provider_name = cfg.web_search_provider.strip().lower()

        logger.info(f"Creating SearchProvider for '{provider_name}'")

        if provider_name in ("duckduckgo", "ddg"):
            return DuckDuckGoSearchProvider()
        else:
            return MockSearchProvider()
