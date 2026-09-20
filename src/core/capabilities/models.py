"""
ASTRA Central Capability Models.
Defines canonical capability taxonomy, risk hierarchy, state lifecycle, and CapabilityDefinition.
"""

from dataclasses import dataclass, field
from enum import Enum, IntEnum
import re
from typing import Any, Optional


class CapabilityCategory(str, Enum):
    """Canonical taxonomy of capability categories."""
    CONVERSATION = "conversation"
    SYSTEM = "system"
    DESKTOP = "desktop"
    FILESYSTEM = "filesystem"
    WEB = "web"
    MEMORY = "memory"
    VISION = "vision"
    TASKS = "tasks"
    AUTOMATION = "automation"
    COMMUNICATION = "communication"
    SECURITY = "security"
    OTHER = "other"


class RiskLevel(IntEnum):
    """
    Capability risk hierarchy.
    Higher values indicate greater potential impact or destructiveness.
    """
    RISK_0 = 0  # Conversation / pure reasoning / no external action
    RISK_1 = 1  # Read-only / observational (e.g. system info, search files, retrieve memory)
    RISK_2 = 2  # Safe or reversible local action (e.g. launch app, create text file, remember)
    RISK_3 = 3  # Meaningful side effect / external communication (e.g. rename file, organize folder)
    RISK_4 = 4  # Destructive or difficult-to-reverse action (e.g. delete file, forget memory)
    RISK_5 = 5  # High-impact / restricted action (e.g. system shutdown, format disk)


class CapabilityState(str, Enum):
    """Lifecycle and operational availability states of a capability."""
    REGISTERED = "REGISTERED"
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    UNAVAILABLE = "UNAVAILABLE"
    DEGRADED = "DEGRADED"


# Capability ID pattern: category.action (e.g. 'system.open_application')
CAPABILITY_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]+(\.[a-zA-Z0-9_\-]+)+$")


@dataclass
class CapabilityDefinition:
    """
    Canonical representation of an ASTRA capability.
    Represents what the system can do, its policies, schemas, and dependencies,
    independently of the concrete tool implementation that executes it.
    """
    capability_id: str
    name: str
    description: str
    version: str = "1.0"
    category: CapabilityCategory = CapabilityCategory.OTHER
    risk_level: RiskLevel = RiskLevel.RISK_2
    input_schema: dict[str, Any] = field(
        default_factory=lambda: {"type": "object", "properties": {}, "required": []}
    )
    output_schema: Optional[dict[str, Any]] = None
    requires_confirmation: bool = False
    requires_elevation: bool = False
    read_only: bool = False
    reversible: bool = False
    supports_undo: bool = False
    platforms: list[str] = field(default_factory=lambda: ["windows"])
    permissions: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    timeout: float = 30.0
    idempotent: bool = False
    tags: list[str] = field(default_factory=list)
    state: CapabilityState = CapabilityState.REGISTERED
    handler: Optional[Any] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Validate ID format
        if not self.capability_id or not isinstance(self.capability_id, str):
            raise ValueError("Capability ID must be a non-empty string.")
        
        normalized_id = self.capability_id.strip().lower()
        if not CAPABILITY_ID_REGEX.match(normalized_id) and "." not in normalized_id:
            raise ValueError(
                f"Invalid capability ID format '{self.capability_id}'. "
                "Must follow dot-separated namespace pattern, e.g. 'system.open_application'."
            )
        self.capability_id = normalized_id

        # Validate name and description
        if not self.name or not self.name.strip():
            raise ValueError("Capability name cannot be empty.")
        if not self.description or not self.description.strip():
            raise ValueError("Capability description cannot be empty.")

        # Normalize category
        if isinstance(self.category, str):
            try:
                self.category = CapabilityCategory(self.category.lower())
            except ValueError:
                self.category = CapabilityCategory.OTHER

        # Normalize risk level
        if not isinstance(self.risk_level, RiskLevel):
            if isinstance(self.risk_level, int):
                self.risk_level = RiskLevel(self.risk_level)
            elif isinstance(self.risk_level, str):
                self.risk_level = RiskLevel[self.risk_level.upper()]

        # Normalize state
        if isinstance(self.state, str):
            self.state = CapabilityState(self.state.upper())

        # Normalize platforms
        self.platforms = [p.lower() for p in self.platforms]

    def is_available_on_platform(self, current_platform: str) -> bool:
        """Check if the capability supports the target platform (e.g. 'windows', 'linux', 'darwin')."""
        curr = current_platform.lower()
        return curr in self.platforms or "all" in self.platforms or "*" in self.platforms

    def is_executable(self) -> bool:
        """Returns True if capability is in an enabled, non-degraded, non-unavailable state."""
        return self.state in (CapabilityState.REGISTERED, CapabilityState.ENABLED)

    def to_dict(self) -> dict[str, Any]:
        """Serialize capability metadata to a dictionary, omitting the internal handler reference."""
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "category": self.category.value,
            "risk_level": self.risk_level.value,
            "risk_name": self.risk_level.name,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "requires_confirmation": self.requires_confirmation,
            "requires_elevation": self.requires_elevation,
            "read_only": self.read_only,
            "reversible": self.reversible,
            "supports_undo": self.supports_undo,
            "platforms": self.platforms,
            "permissions": self.permissions,
            "dependencies": self.dependencies,
            "timeout": self.timeout,
            "idempotent": self.idempotent,
            "tags": self.tags,
            "state": self.state.value,
            "has_handler": self.handler is not None,
            "metadata": self.metadata,
        }
