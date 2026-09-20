"""
Memory Manager Orchestrator (Memory V2).
Central interface for memory persistence, policy enforcement, candidate extraction, and context retrieval.
Provides 100% backward compatibility for Phase 7 callers while delegating to MemoryService.
"""

from typing import Any, Optional
from src.core.config import Config
from src.core.events.bus import EventBus
from src.core.logger import get_logger
from src.memory.extractor import MemoryExtractor
from src.memory.models import (
    MemoryCandidate,
    MemoryExplicitness,
    MemoryImportance,
    MemoryItem,
    MemoryPolicyDecision,
    MemoryScope,
    MemorySearchResult,
    MemorySource,
    MemoryStatus,
    MemoryType,
    RetentionPolicy,
)
from src.memory.policy import MemoryPolicy
from src.memory.repository import MemoryRepository
from src.memory.retriever import MemoryRetriever
from src.memory.service import MemoryService

logger = get_logger()


class MemoryManager:
    """Central Memory Manager orchestrating memory operations with MemoryService integration."""

    def __init__(
        self,
        config: Optional[Config] = None,
        repository: Optional[MemoryRepository] = None,
        policy: Optional[MemoryPolicy] = None,
        extractor: Optional[MemoryExtractor] = None,
        retriever: Optional[MemoryRetriever] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.config = config or Config()
        self.repository = repository or MemoryRepository(config=self.config)
        self.policy = policy or MemoryPolicy(repository=self.repository)
        self.extractor = extractor or MemoryExtractor()
        self.retriever = retriever or MemoryRetriever(repository=self.repository, config=self.config)
        self.event_bus = event_bus

        self.service = MemoryService(
            config=self.config,
            repository=self.repository,
            policy=self.policy,
            event_bus=self.event_bus,
        )

    def remember(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.PROFILE,
        source: MemorySource | str = MemorySource.USER_EXPLICIT,
        importance: MemoryImportance = MemoryImportance.MEDIUM,
        explicitness: MemoryExplicitness = MemoryExplicitness.EXPLICIT,
        retention_policy: Optional[RetentionPolicy] = None,
        scope_type: Optional[MemoryScope] = None,
        project_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
        entities: Optional[list[str]] = None,
        summary: str = "",
        confidence: Optional[float] = None,
        **kwargs: Any,
    ) -> Optional[MemoryItem]:
        """Store a new memory item subject to MemoryPolicy evaluation."""
        resolved_scope = scope_type or (MemoryScope.PROJECT if project_id else MemoryScope.GLOBAL)
        return self.service.remember(
            content=content,
            memory_type=memory_type,
            explicitness=explicitness,
            source=source,
            importance=importance,
            confidence=confidence,
            retention_policy=retention_policy,
            scope_type=resolved_scope,
            project_id=project_id,
            tags=tags,
            entities=entities,
            summary=summary,
            **kwargs,
        )

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

    def retrieve(
        self,
        query: str,
        project_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[MemorySearchResult]:
        """Retrieve relevant memory records for query context."""
        return self.retriever.retrieve_relevant(query=query, project_id=project_id, limit=limit)

    def search(
        self,
        query: str,
        memory_type: Optional[MemoryType] = None,
        limit: int = 10,
    ) -> list[MemoryItem]:
        """Search memory database by keyword query."""
        return self.service.search(query=query, memory_type=memory_type, limit=limit)

    def forget(self, memory_id: str | int, reason: str = "") -> bool:
        """Revoke/Delete specific memory item by ID."""
        return self.service.revoke(memory_id, reason=reason)

    def forget_matching(self, content_pattern: str) -> int:
        """Find and soft-delete memories matching text pattern."""
        matching = self.search(query=content_pattern)
        count = 0
        for item in matching:
            target_id = item.memory_id or item.id
            if target_id and self.service.revoke(target_id):
                count += 1
        return count

    def clear(self, exclude_system: bool = True) -> int:
        """Clear all stored personal memories."""
        return self.repository.clear_all(exclude_system=exclude_system)

    def list_all(
        self,
        status: MemoryStatus = MemoryStatus.ACTIVE,
        scope_type: Optional[MemoryScope] = None,
        project_id: Optional[str] = None,
    ) -> list[MemoryItem]:
        """List all active memory records."""
        return self.service.list_all(status=status, scope_type=scope_type, project_id=project_id)

    def get_stats(self) -> dict[str, int]:
        """Get summary statistics for active memory categories."""
        all_memories = self.service.list_all(status=MemoryStatus.ACTIVE)
        stats = {
            "total": len(all_memories),
            "WORKING": 0,
            "PREFERENCE": 0,
            "PROFILE": 0,
            "PROJECT": 0,
            "EPISODIC": 0,
            "PROCEDURAL": 0,
            # Legacy Phase 7 categories
            "USER_PREFERENCE": 0,
            "USER_FACT": 0,
            "WORKFLOW": 0,
            "TASK": 0,
            "SYSTEM": 0,
        }

        for item in all_memories:
            key = item.type.value if hasattr(item.type, "value") else str(item.type)
            if key in stats:
                stats[key] += 1

        return stats
