"""
Memory Manager Orchestrator.
Central interface for memory persistence, policy enforcement, candidate extraction, and context retrieval.
"""

from typing import Any
from src.core.config import Config
from src.core.logger import get_logger
from src.memory.extractor import MemoryExtractor
from src.memory.models import (
    MemoryCandidate,
    MemoryImportance,
    MemoryItem,
    MemoryPolicyDecision,
    MemorySearchResult,
    MemorySource,
    MemoryStatus,
    MemoryType,
)
from src.memory.policy import MemoryPolicy
from src.memory.repository import MemoryRepository
from src.memory.retriever import MemoryRetriever

logger = get_logger()


class MemoryManager:
    """Central Memory Manager orchestrating memory operations."""

    def __init__(
        self,
        config: Config | None = None,
        repository: MemoryRepository | None = None,
        policy: MemoryPolicy | None = None,
        extractor: MemoryExtractor | None = None,
        retriever: MemoryRetriever | None = None,
    ):
        self.config = config or Config()
        self.repository = repository or MemoryRepository(config=self.config)
        self.policy = policy or MemoryPolicy(repository=self.repository)
        self.extractor = extractor or MemoryExtractor()
        self.retriever = retriever or MemoryRetriever(repository=self.repository, config=self.config)

    def remember(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.USER_FACT,
        source: MemorySource = MemorySource.USER_EXPLICIT,
        importance: MemoryImportance = MemoryImportance.MEDIUM,
        project_id: str | None = None,
        tags: list[str] | None = None,
    ) -> MemoryItem | None:
        """Store a new memory item subject to MemoryPolicy evaluation."""
        candidate = MemoryCandidate(
            content=content.strip(),
            type=memory_type,
            source=source,
            importance=importance,
            project_id=project_id,
            tags=tags or [],
        )

        decision, existing_item = self.policy.evaluate(candidate)

        if decision == MemoryPolicyDecision.DO_NOT_STORE:
            logger.warning(f"MemoryManager: Policy rejected storing memory candidate '{content}'")
            return None

        if decision == MemoryPolicyDecision.UPDATE_EXISTING and existing_item:
            existing_item.content = candidate.content
            existing_item.importance = candidate.importance
            return self.repository.update(existing_item)

        # Default STORE
        new_item = MemoryItem(
            id=None,
            type=candidate.type,
            content=candidate.content,
            source=candidate.source,
            importance=candidate.importance,
            confidence=candidate.confidence,
            status=MemoryStatus.ACTIVE,
            project_id=candidate.project_id,
            tags=candidate.tags,
        )
        return self.repository.add(new_item)

    def extract_and_remember(self, user_statement: str) -> list[MemoryItem]:
        """Extract memory candidates from natural statement and persist approved items."""
        candidates = self.extractor.extract_candidates(user_statement)
        saved_items = []

        for candidate in candidates:
            item = self.remember(
                content=candidate.content,
                memory_type=candidate.type,
                source=candidate.source,
                importance=candidate.importance,
                project_id=candidate.project_id,
                tags=candidate.tags,
            )
            if item:
                saved_items.append(item)

        return saved_items

    def retrieve(self, query: str, project_id: str | None = None, limit: int | None = None) -> list[MemorySearchResult]:
        """Retrieve relevant memory records for query context."""
        return self.retriever.retrieve_relevant(query=query, project_id=project_id, limit=limit)

    def search(self, query: str, memory_type: MemoryType | None = None, limit: int = 10) -> list[MemoryItem]:
        """Search memory database by keyword query."""
        return self.repository.search(query=query, memory_type=memory_type, limit=limit)

    def forget(self, memory_id: int) -> bool:
        """Delete specific memory item by ID."""
        return self.repository.delete(memory_id)

    def forget_matching(self, content_pattern: str) -> int:
        """Find and soft-delete memories matching text pattern."""
        matching = self.repository.search(query=content_pattern)
        count = 0
        for item in matching:
            if item.id and self.repository.delete(item.id):
                count += 1
        return count

    def clear(self, exclude_system: bool = True) -> int:
        """Clear all stored personal memories."""
        return self.repository.clear_all(exclude_system=exclude_system)

    def list_all(self) -> list[MemoryItem]:
        """List all active memory records."""
        return self.repository.list_all()

    def get_stats(self) -> dict[str, int]:
        """Get summary statistics for active memory categories."""
        all_memories = self.repository.list_all()
        stats = {
            "total": len(all_memories),
            "USER_PREFERENCE": 0,
            "USER_FACT": 0,
            "PROJECT": 0,
            "WORKFLOW": 0,
            "TASK": 0,
            "SYSTEM": 0,
        }

        for item in all_memories:
            key = item.type.value if isinstance(item.type, MemoryType) else str(item.type)
            if key in stats:
                stats[key] += 1

        return stats
