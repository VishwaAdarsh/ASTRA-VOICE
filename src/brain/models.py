"""
Core Domain Models for ASTRA.
Defines explicit enums and dataclasses for Commands, Intents, Tool Requests, Results, and Execution Statuses.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ExecutionStatus(str, Enum):
    """Explicit tool and workflow execution statuses."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    DENIED = "DENIED"
    NOT_FOUND = "NOT_FOUND"
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"
    INVALID_REQUEST = "INVALID_REQUEST"


class PermissionLevel(str, Enum):
    """Security classification levels for actions and tools."""

    SAFE = "SAFE"
    CONFIRM = "CONFIRM"
    RESTRICTED = "RESTRICTED"


class IntentType(str, Enum):
    """Supported intent classifications for ASTRA."""

    OPEN_APPLICATION = "OPEN_APPLICATION"
    OPEN_FOLDER = "OPEN_FOLDER"
    OPEN_WEBSITE = "OPEN_WEBSITE"
    SYSTEM_INFORMATION = "SYSTEM_INFORMATION"
    CONVERSATION = "CONVERSATION"
    WEB_SEARCH = "WEB_SEARCH"
    MEMORY = "MEMORY"
    STOP = "STOP"
    UNKNOWN = "UNKNOWN"



@dataclass(frozen=True)
class Command:
    """Represents a raw user input command."""

    raw_text: str
    normalized_text: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Intent:
    """Represents the recognized intent and extracted parameters."""

    intent_type: IntentType
    confidence: float
    parameters: dict[str, Any] = field(default_factory=dict)
    raw_command: str = ""


@dataclass
class ToolRequest:
    """Represents a structured request to invoke a specific tool."""

    tool_name: str
    parameters: dict[str, Any] = field(default_factory=dict)
    intent: Intent | None = None


@dataclass
class ToolResult:
    """Represents the result returned by a tool execution."""

    status: ExecutionStatus
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    execution_time_ms: float = 0.0
    verified: bool = False

