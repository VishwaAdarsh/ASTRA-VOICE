"""
Memory Service Subsystem (Memory V2).
Central business logic, lifecycle management, conflict resolution, and Event Bus integration for ASTRA Memory.
"""

from typing import Any, Optional
from src.core.config import Config
from src.core.events.bus import EventBus
from src.core.events.models import ASTRAEvent, AstraEventType
from src.core.logger import get_logger
from src.memory.models import (
    MemoryCandidate,
    MemoryExplicitness,
    MemoryImportance,
    MemoryItem,
    MemoryPolicyDecision,
    MemoryScope,
    MemorySource,
    MemoryStatus,
    MemoryType,
    RetentionPolicy,
)
from src.memory.policy import MemoryPolicy
from src.memory.repository import MemoryRepository
from src.security.auditor import SecretRedactionFilter

logger = get_logger()


class MemoryService:
    """
    Central business logic orchestrator for Memory V2.
    Coordinates validation, deduplication, conflict resolution, persistence, and safe event emission.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        repository: Optional[MemoryRepository] = None,
        policy: Optional[MemoryPolicy] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.config = config or Config()
        self.repository = repository or MemoryRepository(config=self.config)
        self.policy = policy or MemoryPolicy(repository=self.repository)
        if self.policy and not self.policy.repository:
            self.policy.repository = self.repository
        self.event_bus = event_bus

    def remember(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.PROFILE,
        explicitness: Optional[MemoryExplicitness] = None,
        source: MemorySource | str = MemorySource.USER_EXPLICIT,
        importance: MemoryImportance = MemoryImportance.MEDIUM,
        confidence: Optional[float] = None,
        retention_policy: Optional[RetentionPolicy] = None,
        scope_type: MemoryScope = MemoryScope.GLOBAL,
        scope_id: str = "",
        project_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
        entities: Optional[list[str]] = None,
        summary: str = "",
        source_reference: str = "",
        source_ref: str = "",
        request_id: str = "",
    ) -> Optional[MemoryItem]:
        """
        Store a new memory item subject to policy, deduplication, and conflict resolution.
        """
        # Resolve source reference
        ref = source_ref or source_reference

        # Determine explicitness from source if not explicitly provided
        if explicitness is None:
            if isinstance(source, MemorySource):
                explicitness = MemoryExplicitness.EXPLICIT if source == MemorySource.USER_EXPLICIT else MemoryExplicitness.INFERRED
            else:
                explicitness = MemoryExplicitness.EXPLICIT if str(source) == "USER_EXPLICIT" else MemoryExplicitness.INFERRED

        # Determine default confidence & retention based on explicitness
        if confidence is None:
            confidence = 1.0 if explicitness == MemoryExplicitness.EXPLICIT else 0.75

        # Clamp confidence to [0.0, 1.0]
        confidence = max(0.0, min(1.0, float(confidence)))

        if retention_policy is None:
            retention_policy = (
                RetentionPolicy.PERMANENT
                if explicitness == MemoryExplicitness.EXPLICIT
                else RetentionPolicy.TIME_BOUND
            )

        # Redact secrets before policy evaluation and persistence
        clean_content = SecretRedactionFilter.redact(content.strip())

        candidate = MemoryCandidate(
            content=clean_content,
            type=memory_type,
            source=source,
            summary=summary,
            importance=importance,
            confidence=confidence,
            explicitness=explicitness,
            retention_policy=retention_policy,
            scope_type=scope_type,
            scope_id=scope_id or (project_id or ""),
            project_id=project_id,
            tags=tags or [],
            entities=entities or [],
            source_reference=ref,
            source_ref=ref,
            created_from_request_id=request_id,
        )

        # 1. Policy Evaluation
        decision, existing_item = self.policy.evaluate(candidate)

        if decision == MemoryPolicyDecision.DO_NOT_STORE:
            if existing_item:
                # Deduplication hit: return the existing matching item
                return existing_item
            logger.info(f"MemoryService: Policy rejected storing memory candidate: '{content[:50]}'")
            return None

        # 2. Conflict Handling / Superseding
        if decision == MemoryPolicyDecision.UPDATE_EXISTING and existing_item:
            # Supersede the older conflicting memory
            new_item = MemoryItem(
                id=None,
                type=candidate.type,
                content=candidate.content,
                summary=candidate.summary,
                source=candidate.source,
                source_reference=candidate.source_reference,
                source_ref=candidate.source_reference,
                created_from_request_id=candidate.created_from_request_id,
                importance=candidate.importance,
                confidence=candidate.confidence,
                explicitness=candidate.explicitness,
                retention_policy=candidate.retention_policy,
                status=MemoryStatus.ACTIVE,
                scope_type=candidate.scope_type,
                scope_id=candidate.scope_id,
                project_id=candidate.project_id,
                tags=candidate.tags,
                entities=candidate.entities,
            )
            saved_item = self.repository.add(new_item)

            # Mark existing item as SUPERSEDED
            old_target = existing_item.memory_id or str(existing_item.id)
            self.repository.supersede(old_target, saved_item.memory_id)

            self._publish_event(
                AstraEventType.MEMORY_SUPERSEDED,
                {
                    "old_memory_id": old_target,
                    "new_memory_id": saved_item.memory_id,
                    "type": saved_item.type.value,
                    "request_id": request_id,
                },
            )
            return saved_item

        # 3. Standard Store
        new_item = MemoryItem(
            id=None,
            type=candidate.type,
            content=candidate.content,
            summary=candidate.summary,
            source=candidate.source,
            source_reference=candidate.source_reference,
            source_ref=candidate.source_reference,
            created_from_request_id=candidate.created_from_request_id,
            importance=candidate.importance,
            confidence=candidate.confidence,
            explicitness=candidate.explicitness,
            retention_policy=candidate.retention_policy,
            status=MemoryStatus.ACTIVE,
            scope_type=candidate.scope_type,
            scope_id=candidate.scope_id,
            project_id=candidate.project_id,
            tags=candidate.tags,
            entities=candidate.entities,
        )
        saved = self.repository.add(new_item)

        self._publish_event(
            AstraEventType.MEMORY_CREATED,
            {
                "memory_id": saved.memory_id,
                "type": saved.type.value,
                "explicitness": saved.explicitness.value,
                "scope_type": saved.scope_type.value,
                "request_id": request_id,
            },
        )
        return saved

    def create(self, *args, **kwargs) -> Optional[MemoryItem]:
        """Alias for remember()."""
        return self.remember(*args, **kwargs)

    def get(self, memory_id: str | int, include_revoked: bool = True) -> Optional[MemoryItem]:
        """Retrieve memory by stable string memory_id or legacy integer id."""
        return self.repository.get_by_id(memory_id, include_revoked=include_revoked)

    def update(self, item: MemoryItem, request_id: str = "") -> MemoryItem:
        """Update existing memory item."""
        updated = self.repository.update(item)
        self._publish_event(
            AstraEventType.MEMORY_UPDATED,
            {
                "memory_id": updated.memory_id,
                "type": updated.type.value,
                "status": updated.status.value,
                "request_id": request_id,
            },
        )
        return updated

    def revoke(self, memory_id: str | int, reason: str = "", request_id: str = "") -> bool:
        """Revoke a stored memory item."""
        success = self.repository.revoke(memory_id, reason=reason)
        if success:
            self._publish_event(
                AstraEventType.MEMORY_REVOKED,
                {
                    "memory_id": str(memory_id),
                    "reason": reason,
                    "request_id": request_id,
                },
            )
        return success

    def confirm(self, memory_id: str | int, request_id: str = "") -> Optional[MemoryItem]:
        """Confirm an inferred or existing memory item."""
        success = self.repository.confirm(memory_id)
        if success:
            self._publish_event(
                AstraEventType.MEMORY_CONFIRMED,
                {
                    "memory_id": str(memory_id),
                    "request_id": request_id,
                },
            )
            return self.repository.get_by_id(memory_id)
        return None

    def cleanup_expired(self) -> int:
        """Evaluate and mark expired memories."""
        return self.repository.cleanup_expired()

    def search(
        self,
        query: str = "",
        memory_type: Optional[MemoryType] = None,
        scope_type: Optional[MemoryScope] = None,
        project_id: Optional[str] = None,
        status: MemoryStatus = MemoryStatus.ACTIVE,
        limit: int = 10,
    ) -> list[MemoryItem]:
        """Search active memory items with filtering."""
        try:
            return self.repository.search(
                query=query,
                memory_type=memory_type,
                scope_type=scope_type,
                project_id=project_id,
                status=status,
                limit=limit,
            )
        except Exception as e:
            logger.error(f"MemoryService: Search failed for '{query}': {e}")
            self._publish_event(
                AstraEventType.MEMORY_RETRIEVAL_FAILED,
                {"query": query[:50], "error": str(e)},
            )
            return []

    def list_all(
        self,
        status: MemoryStatus = MemoryStatus.ACTIVE,
        scope_type: Optional[MemoryScope] = None,
        project_id: Optional[str] = None,
    ) -> list[MemoryItem]:
        """List all memories matching specified status and scope."""
        return self.repository.list_all(
            status=status,
            scope_type=scope_type,
            project_id=project_id,
        )

    def cleanup(self) -> int:
        """Perform lifecycle maintenance and clean up expired memories."""
        count = self.repository.cleanup_expired()
        if count > 0:
            self._publish_event(
                AstraEventType.MEMORY_EXPIRED,
                {"expired_count": count},
            )
        return count

    def _publish_event(self, event_type: Any, payload: dict[str, Any]) -> None:
        """Publish safe metadata event to EventBus if available."""
        if not self.event_bus:
            return
        try:
            self.event_bus.publish(
                ASTRAEvent(
                    event_type=event_type,
                    source="memory_service",
                    payload=payload,
                )
            )
        except Exception as e:
            logger.warning(f"MemoryService: Failed to publish event '{event_type}': {e}")
