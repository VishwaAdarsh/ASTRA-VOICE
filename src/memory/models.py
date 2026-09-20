"""
Memory Subsystem Models, Enums, and Dataclasses (Memory V2).
Defines canonical structured models for persistent, context-aware, and privacy-safe memory.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
import uuid


class MemoryType(str, Enum):
    """Categorical types of long-term memory."""

    # Core V2 Types
    WORKING = "WORKING"
    PREFERENCE = "PREFERENCE"
    PROFILE = "PROFILE"
    PROJECT = "PROJECT"
    EPISODIC = "EPISODIC"
    PROCEDURAL = "PROCEDURAL"

    # Legacy Phase 7 Aliases (backward compatibility)
    USER_PREFERENCE = "PREFERENCE"
    USER_FACT = "PROFILE"
    WORKFLOW = "PROCEDURAL"
    TASK = "EPISODIC"
    SYSTEM = "PROFILE"

    @classmethod
    def _missing_(cls, value: object):
        """Handle legacy string values and case-insensitive lookups."""
        if isinstance(value, str):
            val_upper = value.strip().upper()
            legacy_map = {
                "USER_PREFERENCE": cls.PREFERENCE,
                "USER_FACT": cls.PROFILE,
                "WORKFLOW": cls.PROCEDURAL,
                "TASK": cls.EPISODIC,
                "SYSTEM": cls.PROFILE,
            }
            if val_upper in legacy_map:
                return legacy_map[val_upper]
            for member in cls:
                if member.value == val_upper:
                    return member
        return None

    @classmethod
    def normalize(cls, val: Any) -> "MemoryType":
        """Normalize legacy or lowercase types to canonical V2 types."""
        if isinstance(val, cls):
            return val

        val_str = str(val).strip().upper()
        res = cls._missing_(val_str)
        if res is not None:
            return res
        if hasattr(cls, val_str):
            return getattr(cls, val_str)
        return cls.PROFILE


class MemoryExplicitness(str, Enum):
    """Distinguishes whether a memory was directly stated or inferred."""

    EXPLICIT = "EXPLICIT"
    INFERRED = "INFERRED"


class RetentionPolicy(str, Enum):
    """Retention duration and lifecycle rules for memories."""

    PERMANENT = "PERMANENT"
    SESSION_BOUND = "SESSION_BOUND"
    TIME_BOUND = "TIME_BOUND"
    ACCESSED_RECENTLY = "ACCESSED_RECENTLY"
    AUTO_CLEANUP = "AUTO_CLEANUP"

    # Backward compatibility aliases
    SESSION = "SESSION_BOUND"
    SHORT = "TIME_BOUND"
    MEDIUM = "TIME_BOUND"
    LONG = "PERMANENT"
    PERSISTENT_UNTIL_CHANGED = "PERMANENT"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            val_upper = value.strip().upper()
            mapping = {
                "SESSION": cls.SESSION_BOUND,
                "SHORT": cls.TIME_BOUND,
                "MEDIUM": cls.TIME_BOUND,
                "LONG": cls.PERMANENT,
                "PERSISTENT_UNTIL_CHANGED": cls.PERMANENT,
            }
            if val_upper in mapping:
                return mapping[val_upper]
            for member in cls:
                if member.value == val_upper:
                    return member
        return None


class MemoryScope(str, Enum):
    """Context scope bounding a memory item."""

    GLOBAL = "GLOBAL"
    PROJECT = "PROJECT"
    SESSION = "SESSION"


class MemorySource(str, Enum):
    """Source origin of memory entries."""

    USER_EXPLICIT = "USER_EXPLICIT"
    CONVERSATION_INFERRED = "CONVERSATION_INFERRED"
    DESKTOP_INFERRED = "DESKTOP_INFERRED"
    TOOL_OUTPUT = "TOOL_OUTPUT"
    SYSTEM = "SYSTEM"

    # Backward compatibility aliases
    USER_CONVERSATION = "CONVERSATION_INFERRED"
    SYSTEM_CONTEXT = "SYSTEM"
    PROJECT_DOCUMENT = "TOOL_OUTPUT"
    INFERENCE = "CONVERSATION_INFERRED"
    SYSTEM_CONFIGURATION = "SYSTEM"
    PROJECT_CONFIGURATION = "TOOL_OUTPUT"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            val_upper = value.strip().upper()
            mapping = {
                "USER_CONVERSATION": cls.CONVERSATION_INFERRED,
                "SYSTEM_CONTEXT": cls.SYSTEM,
                "PROJECT_DOCUMENT": cls.TOOL_OUTPUT,
                "INFERENCE": cls.CONVERSATION_INFERRED,
                "SYSTEM_CONFIGURATION": cls.SYSTEM,
                "PROJECT_CONFIGURATION": cls.TOOL_OUTPUT,
            }
            if val_upper in mapping:
                return mapping[val_upper]
            for member in cls:
                if member.value == val_upper:
                    return member
        return None


class MemoryImportance(str, Enum):
    """Importance weighting scale for memories."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class MemoryStatus(str, Enum):
    """Lifecycle state of memory items."""

    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"
    ARCHIVED = "ARCHIVED"
    REVOKED = "REVOKED"
    DELETED = "DELETED"  # Legacy alias for REVOKED/DELETED


class MemoryPolicyDecision(str, Enum):
    """Action outcome decided by MemoryPolicy."""

    STORE = "STORE"
    DO_NOT_STORE = "DO_NOT_STORE"
    UPDATE_EXISTING = "UPDATE_EXISTING"
    SUPERSEDE_EXISTING = "SUPERSEDE_EXISTING"
    ASK_USER = "ASK_USER"
    DELETE_EXISTING = "DELETE_EXISTING"


@dataclass
class MemoryItem:
    """Structured canonical long-term memory record (Memory V2)."""

    id: int | None = None
    memory_id: str = ""
    type: MemoryType = MemoryType.PROFILE
    content: str = ""
    summary: str = ""
    source: MemorySource | str = MemorySource.USER_EXPLICIT
    source_reference: str = ""
    source_ref: str = ""
    created_from_request_id: str = ""
    importance: MemoryImportance = MemoryImportance.MEDIUM
    confidence: float = 1.0
    explicitness: MemoryExplicitness = MemoryExplicitness.EXPLICIT
    retention_policy: RetentionPolicy = RetentionPolicy.PERMANENT
    status: MemoryStatus = MemoryStatus.ACTIVE
    scope_type: MemoryScope = MemoryScope.GLOBAL
    scope_id: str = ""
    project_id: str | None = None
    memory_type: MemoryType | None = None
    tags: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    privacy_level: str = "NORMAL"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_accessed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_confirmed_at: str | None = None
    expires_at: str | None = None
    access_count: int = 0
    superseded_by: str | None = None
    revocation_reason: str | None = None

    def __post_init__(self):
        if not self.memory_id:
            self.memory_id = f"mem_{uuid.uuid4().hex[:12]}"

        if self.memory_type is not None:
            self.type = self.memory_type
        elif self.type is not None:
            self.memory_type = self.type

        if self.source_ref and not self.source_reference:
            self.source_reference = self.source_ref
        elif self.source_reference and not self.source_ref:
            self.source_ref = self.source_reference

        # Sync scope_type if project_id is provided
        if self.project_id and self.scope_type == MemoryScope.GLOBAL:
            self.scope_type = MemoryScope.PROJECT
            self.scope_id = self.project_id

        # Normalize enum types if string passed
        if isinstance(self.type, str):
            try:
                self.type = MemoryType(self.type)
            except ValueError:
                self.type = MemoryType.PROFILE

        if isinstance(self.explicitness, str):
            try:
                self.explicitness = MemoryExplicitness(self.explicitness)
            except ValueError:
                self.explicitness = MemoryExplicitness.EXPLICIT

        if isinstance(self.retention_policy, str):
            try:
                self.retention_policy = RetentionPolicy(self.retention_policy)
            except ValueError:
                self.retention_policy = RetentionPolicy.PERMANENT

        if isinstance(self.scope_type, str):
            try:
                self.scope_type = MemoryScope(self.scope_type)
            except ValueError:
                self.scope_type = MemoryScope.GLOBAL

        if isinstance(self.status, str):
            try:
                self.status = MemoryStatus(self.status)
            except ValueError:
                self.status = MemoryStatus.ACTIVE

        if isinstance(self.importance, str):
            try:
                self.importance = MemoryImportance(self.importance)
            except ValueError:
                self.importance = MemoryImportance.MEDIUM

    def to_dict(self) -> dict[str, Any]:
        """Serialize memory item to dictionary."""
        return {
            "id": self.id,
            "memory_id": self.memory_id,
            "type": self.type.value if hasattr(self.type, "value") else str(self.type),
            "memory_type": self.type.value if hasattr(self.type, "value") else str(self.type),
            "content": self.content,
            "summary": self.summary,
            "source": self.source.value if hasattr(self.source, "value") else str(self.source),
            "source_reference": self.source_reference,
            "source_ref": self.source_reference,
            "created_from_request_id": self.created_from_request_id,
            "importance": self.importance.value if hasattr(self.importance, "value") else str(self.importance),
            "confidence": self.confidence,
            "explicitness": self.explicitness.value if hasattr(self.explicitness, "value") else str(self.explicitness),
            "retention_policy": self.retention_policy.value if hasattr(self.retention_policy, "value") else str(self.retention_policy),
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "scope_type": self.scope_type.value if hasattr(self.scope_type, "value") else str(self.scope_type),
            "scope_id": self.scope_id,
            "project_id": self.project_id,
            "tags": self.tags,
            "entities": self.entities,
            "privacy_level": self.privacy_level,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_accessed_at": self.last_accessed_at,
            "last_confirmed_at": self.last_confirmed_at,
            "expires_at": self.expires_at,
            "access_count": self.access_count,
            "superseded_by": self.superseded_by,
            "revocation_reason": self.revocation_reason,
            "metadata": self.metadata,
        }


@dataclass
class MemoryCandidate:
    """Detected candidate for memory persistence before policy evaluation."""

    content: str
    type: MemoryType = MemoryType.PROFILE
    memory_type: MemoryType | None = None
    source: MemorySource | str = MemorySource.USER_EXPLICIT
    summary: str = ""
    importance: MemoryImportance = MemoryImportance.MEDIUM
    confidence: float = 0.8
    explicitness: MemoryExplicitness = MemoryExplicitness.EXPLICIT
    retention_policy: RetentionPolicy = RetentionPolicy.PERMANENT
    scope_type: MemoryScope = MemoryScope.GLOBAL
    scope_id: str = ""
    reason: str = ""
    project_id: str | None = None
    tags: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    source_reference: str = ""
    source_ref: str = ""
    created_from_request_id: str = ""

    def __post_init__(self):
        if self.memory_type is not None:
            self.type = self.memory_type
        elif self.type is not None:
            self.memory_type = self.type

        if self.source_ref and not self.source_reference:
            self.source_reference = self.source_ref
        elif self.source_reference and not self.source_ref:
            self.source_ref = self.source_reference


@dataclass
class MemorySearchQuery:
    """Query parameters for searching memory records."""

    query: str
    memory_type: MemoryType | None = None
    scope_type: MemoryScope | None = None
    project_id: str | None = None
    status: MemoryStatus = MemoryStatus.ACTIVE
    limit: int = 10


@dataclass
class MemorySearchResult:
    """Search result wrapper containing memory item and relevance score."""

    memory: MemoryItem
    relevance_score: float = 1.0
