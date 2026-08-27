"""
ASTRA Domain Exception Hierarchy.
All application-specific exceptions inherit from AstraError.
"""


class AstraError(Exception):
    """Base exception for all ASTRA errors."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(AstraError):
    """Raised when application configuration is invalid or missing."""

    pass


class IntentRecognitionError(AstraError):
    """Raised when an intent cannot be recognized or parsed."""

    pass


class ToolError(AstraError):
    """Base exception for tool-related errors."""

    pass


class ToolNotFoundError(ToolError):
    """Raised when a requested tool is not found in the ToolRegistry."""

    def __init__(self, tool_name: str):
        super().__init__(f"Tool '{tool_name}' is not registered in ASTRA ToolRegistry.")
        self.tool_name = tool_name


class InvalidParametersError(ToolError):
    """Raised when tool input validation fails."""

    pass


class ToolExecutionError(ToolError):
    """Raised when tool execution encounters an error."""

    pass


class PermissionDeniedError(AstraError):
    """Raised when an action is blocked by the Permission System."""

    def __init__(self, action_name: str, permission_level: str):
        super().__init__(
            f"Permission denied for action '{action_name}'. Required level: {permission_level}"
        )
        self.action_name = action_name
        self.permission_level = permission_level


class VerificationError(AstraError):
    """Raised when pre/post tool verification fails."""

    pass


# LLM Subsystem Exceptions (Phase 4)
class LLMError(AstraError):
    """Base exception for LLM Subsystem errors."""

    pass


class LLMProviderError(LLMError):
    """Raised when an LLM provider API call fails or times out."""

    pass


class LLMValidationError(LLMError):
    """Raised when LLM output fails schema or safety validation."""

    pass


class ContextWindowOverflowError(LLMError):
    """Raised when conversation context exceeds maximum token window."""

    pass


# Advanced Computer & File Control Exceptions (Phase 5)
class FilesystemError(ToolError):
    """Base exception for filesystem operations."""

    pass


class PathSecurityError(FilesystemError):
    """Raised when a path fails security policy validation (e.g. path traversal or restricted system paths)."""

    pass


class FileCollisionError(FilesystemError):
    """Raised when a file operation encounters an unexpected destination collision."""

    pass


class ApplicationNotFoundError(ToolError):
    """Raised when an application executable or process cannot be located."""

    pass


# Web Intelligence & Browser Research Exceptions (Phase 6)
class WebError(ToolError):
    """Base exception for web operations."""

    pass


class WebSearchError(WebError):
    """Raised when a web search request fails."""

    pass


class WebFetchError(WebError):
    """Raised when retrieving a webpage fails or times out."""

    pass


class SSRFSecurityError(WebError):
    """Raised when a URL targets a private IP, loopback, or invalid scheme."""

    pass


class SourceValidationError(WebError):
    """Raised when a research claim fails source validation."""

    pass


# Memory & Personal Context Exceptions (Phase 7)
class MemoryError(ToolError):
    """Base exception for memory operations."""

    pass


class MemoryNotFoundError(MemoryError):
    """Raised when a requested memory item is not found."""

    pass


class SecretFilteringError(MemoryError):
    """Raised when a memory candidate is blocked due to secret credential policies."""

    pass


class MemoryDatabaseError(MemoryError):
    """Raised when SQLite database operations fail."""

    pass
