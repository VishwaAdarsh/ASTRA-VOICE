"""
ASTRA Capability Exception Hierarchy.
Structured error types for capability registration, resolution, validation, and execution.
"""

from typing import Any
from src.core.exceptions import AstraError


class CapabilityError(AstraError):
    """Base exception for all capability-related errors."""

    def __init__(self, message: str, capability_id: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(message, details=details)
        self.capability_id = capability_id


class DuplicateCapabilityError(CapabilityError):
    """Raised when attempting to register a capability with an ID that already exists."""

    def __init__(self, capability_id: str):
        super().__init__(
            f"Capability with ID '{capability_id}' is already registered.",
            capability_id=capability_id,
        )


class CapabilityNotFoundError(CapabilityError):
    """Raised when a requested capability ID cannot be found in the registry."""

    def __init__(self, capability_id: str):
        super().__init__(
            f"Capability '{capability_id}' not found in CapabilityRegistry.",
            capability_id=capability_id,
        )


class CapabilityDisabledError(CapabilityError):
    """Raised when attempting to access or execute a disabled capability."""

    def __init__(self, capability_id: str):
        super().__init__(
            f"Capability '{capability_id}' is currently disabled.",
            capability_id=capability_id,
        )


class CapabilityUnavailableError(CapabilityError):
    """Raised when a capability is currently unavailable due to missing dependencies or unhealthy subsystem."""

    def __init__(self, capability_id: str, reason: str = "Subsystem or dependency unavailable"):
        super().__init__(
            f"Capability '{capability_id}' is currently unavailable: {reason}",
            capability_id=capability_id,
            details={"reason": reason},
        )


class CapabilityUnsupportedPlatformError(CapabilityError):
    """Raised when a capability is invoked on an unsupported operating system."""

    def __init__(self, capability_id: str, current_platform: str, supported_platforms: list[str]):
        super().__init__(
            f"Capability '{capability_id}' is not supported on platform '{current_platform}'. "
            f"Supported platforms: {supported_platforms}",
            capability_id=capability_id,
            details={"platform": current_platform, "supported": supported_platforms},
        )


class CapabilityValidationError(CapabilityError):
    """Raised when input parameters fail validation against the capability's input schema."""

    def __init__(self, capability_id: str, validation_errors: list[str]):
        errors_str = "; ".join(validation_errors)
        super().__init__(
            f"Validation failed for capability '{capability_id}': {errors_str}",
            capability_id=capability_id,
            details={"errors": validation_errors},
        )
        self.validation_errors = validation_errors


class CapabilityPermissionDeniedError(CapabilityError):
    """Raised when a capability execution is denied by security policy."""

    def __init__(self, capability_id: str, reason: str = "Permission denied by security policy"):
        super().__init__(
            f"Execution of capability '{capability_id}' denied: {reason}",
            capability_id=capability_id,
            details={"reason": reason},
        )


class CapabilityConfirmationRequiredError(CapabilityError):
    """Raised when a capability requires interactive user confirmation before execution."""

    def __init__(self, capability_id: str, prompt: str):
        super().__init__(
            f"Capability '{capability_id}' requires user confirmation: {prompt}",
            capability_id=capability_id,
            details={"prompt": prompt},
        )
        self.prompt = prompt


class CapabilityResolutionError(CapabilityError):
    """Raised when a capability ID cannot be resolved to an executable handler."""

    def __init__(self, capability_id: str, reason: str):
        super().__init__(
            f"Failed to resolve handler for capability '{capability_id}': {reason}",
            capability_id=capability_id,
            details={"reason": reason},
        )


class CapabilityExecutionError(CapabilityError):
    """Raised when an unhandled error occurs during capability handler execution."""

    def __init__(self, capability_id: str, original_error: Exception):
        super().__init__(
            f"Execution error in capability '{capability_id}': {original_error}",
            capability_id=capability_id,
            details={"original_error": str(original_error)},
        )
        self.original_error = original_error
