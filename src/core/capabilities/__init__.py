"""
ASTRA Central Capability Subsystem (Phase V2-10).
Exports canonical capability models, registry, resolver, validation, and schemas.
"""

from src.core.capabilities.errors import (
    CapabilityConfirmationRequiredError,
    CapabilityDisabledError,
    CapabilityError,
    CapabilityExecutionError,
    CapabilityNotFoundError,
    CapabilityPermissionDeniedError,
    CapabilityResolutionError,
    CapabilityUnavailableError,
    CapabilityUnsupportedPlatformError,
    CapabilityValidationError,
    DuplicateCapabilityError,
)
from src.core.capabilities.models import (
    CapabilityCategory,
    CapabilityDefinition,
    CapabilityState,
    RiskLevel,
)
from src.core.capabilities.registry import CapabilityRegistry
from src.core.capabilities.resolver import CapabilityResolver
from src.core.capabilities.schemas import LLMToolSchemaAdapter
from src.core.capabilities.validation import SchemaValidator

__all__ = [
    # Models & Enums
    "CapabilityCategory",
    "RiskLevel",
    "CapabilityState",
    "CapabilityDefinition",
    # Registry & Resolver
    "CapabilityRegistry",
    "CapabilityResolver",
    # Schema & Validation
    "LLMToolSchemaAdapter",
    "SchemaValidator",
    # Errors
    "CapabilityError",
    "DuplicateCapabilityError",
    "CapabilityNotFoundError",
    "CapabilityDisabledError",
    "CapabilityUnavailableError",
    "CapabilityUnsupportedPlatformError",
    "CapabilityValidationError",
    "CapabilityPermissionDeniedError",
    "CapabilityConfirmationRequiredError",
    "CapabilityResolutionError",
    "CapabilityExecutionError",
]
