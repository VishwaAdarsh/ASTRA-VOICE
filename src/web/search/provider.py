"""
Abstract Search Provider Interface.
"""

from abc import ABC, abstractmethod
from src.web.models import SearchRequest, SearchResult


class SearchProvider(ABC):
    """Abstract interface for provider-independent web search engines."""

    @abstractmethod
    def search(self, request: SearchRequest) -> list[SearchResult]:
        """Execute web search and return structured search results."""
        pass
