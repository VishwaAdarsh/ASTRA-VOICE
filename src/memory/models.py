"""
Memory Subsystem Models and Enums.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MemoryType(str, Enum):
    """Categorical types of long-term memory."""

    USER_PREFERENCE = "USER_PREFERENCE"
    USER_FACT = "USER_FACT"
    PROJECT = "PROJECT"
    WORKFLOW = "WORKFLOW"
    TASK = "TASK"
    SYSTEM = "SYSTEM"


class MemorySource(str, Enum):
    """Source origin of memory entries."""

    USER_EXPLICIT = "USER_EXPLICIT"
    USER_CONVERSATION = "USER_CONVERSATION"
    SYSTEM_CONFIGURATION = "SYSTEM_CONFIGURATION"
    PROJECT_CONFIGURATION = "PROJECT_CONFIGURATION"


class MemoryImportance(str, Enum):
    """Importance weighting scale for memories."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class MemoryStatus(str, Enum):
    """Lifecycle state of memory items."""

    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"


class MemoryPolicyDecision(str, Enum):
    """Action outcome decided by MemoryPolicy."""

    STORE = "STORE"
    DO_NOT_STORE = "DO_NOT_STORE"
    UPDATE_EXISTING = "UPDATE_EXISTING"
    ASK_USER = "ASK_USER"
    DELETE_EXISTING = "DELETE_EXISTING"


@dataclass
class MemoryItem:
    """Structured long-term memory record."""

    id: int | None
    type: MemoryType
    content: str
    source: MemorySource
    importance: MemoryImportance = MemoryImportance.MEDIUM
    confidence: float = 1.0
    status: MemoryStatus = MemoryStatus.ACTIVE
    project_id: str | None = None
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_accessed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: str | None = None
    access_count: int = 0


@dataclass
class MemoryCandidate:
    """Detected candidate for memory persistence before policy evaluation."""

    content: str
    type: MemoryType
    source: MemorySource
    importance: MemoryImportance = MemoryImportance.MEDIUM
    confidence: float = 0.8
    reason: str = ""
    project_id: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class MemorySearchQuery:
    """Query parameters for searching memory records."""

    query: str
    memory_type: MemoryType | None = None
    project_id: str | None = None
    limit: int = 10


@dataclass
class MemorySearchResult:
    """Search result wrapper containing memory item and relevance score."""

    memory: MemoryItem
    relevance_score: float = 1.0
