"""
Web Cache Manager Subsystem.
Short-term in-memory caching for search results and webpage extractions with TTL expiration.
"""

import time
from typing import Any


class WebCacheManager:
    """In-memory cache container for web responses."""

    def __init__(self, ttl_seconds: int = 3600):
        self.ttl = ttl_seconds
        self._cache: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        """Retrieve cached entry if not expired."""
        if key not in self._cache:
            return None

        timestamp, value = self._cache[key]
        if time.time() - timestamp > self.ttl:
            del self._cache[key]
            return None

        return value

    def set(self, key: str, value: Any) -> None:
        """Store value in cache with current timestamp."""
        self._cache[key] = (time.time(), value)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
