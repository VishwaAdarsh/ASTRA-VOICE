"""
Memory Retriever Subsystem.
Query-driven memory retrieval, scoring, ranking, and context truncation.
"""

from src.core.config import Config
from src.core.logger import get_logger
from src.memory.models import MemoryItem, MemorySearchResult
from src.memory.repository import MemoryRepository

logger = get_logger()


class MemoryRetriever:
    """Retrieves and ranks relevant memory records for query contexts."""

    def __init__(self, repository: MemoryRepository, config: Config | None = None):
        self.repository = repository
        self.config = config or Config()

    def retrieve_relevant(self, query: str, project_id: str | None = None, limit: int | None = None) -> list[MemorySearchResult]:
        """Search and rank memory records relevant to query."""
        max_limit = limit or self.config.max_retrieved_memories
        all_active = self.repository.list_all()

        query_terms = set(query.lower().split()) if query else set()
        results: list[MemorySearchResult] = []

        for item in all_active:
            score = 0.5  # Base relevance

            # Query keyword matches
            content_words = set(item.content.lower().split())
            overlap = query_terms.intersection(content_words) if query_terms else set()
            if overlap:
                score += len(overlap) * 0.3

            # Importance weighting
            if item.importance.value == "HIGH":
                score += 0.3
            elif item.importance.value == "MEDIUM":
                score += 0.1

            # Project matching
            if project_id and item.project_id == project_id:
                score += 0.4

            # Return items with positive relevance
            if not query_terms or overlap or score > 0.6:
                results.append(MemorySearchResult(memory=item, relevance_score=round(score, 2)))
                self.repository.touch(item.id)

        # Sort descending by relevance score
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results[:max_limit]
