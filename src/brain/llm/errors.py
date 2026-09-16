"""
ASTRA LLM Subsystem Error Taxonomy & Typed Exceptions.
Defines explicit classification categories and structured exceptions for provider failures.
"""

from enum import Enum
from typing import Any
from src.core.exceptions import AstraError


class LLMErrorType(str, Enum):
    """Explicit classification categories for LLM provider errors."""

    AUTH_FAILED = "AUTH_FAILED"
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT = "TIMEOUT"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INVALID_REQUEST = "INVALID_REQUEST"
    CONTENT_POLICY_ERROR = "CONTENT_POLICY_ERROR"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class LLMProviderError(AstraError):
    """
    Base typed exception for all LLM provider failures.
    Encapsulates category, HTTP/API status code, retryability, and retry delays.
    """

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        error_type: LLMErrorType = LLMErrorType.PROVIDER_ERROR,
        status_code: int | None = None,
        retryable: bool = False,
        retry_after: float | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details)
        self.provider = provider
        self.error_type = error_type
        self.status_code = status_code
        self.retryable = retryable
        self.retry_after = retry_after
        self.details = details or {}

    def __str__(self) -> str:
        parts = [f"[{self.error_type.value}] {self.message}"]
        if self.provider:
            parts.append(f"(Provider: {self.provider})")
        if self.status_code:
            parts.append(f"(Status: {self.status_code})")
        if self.retry_after:
            parts.append(f"(Retry-After: {self.retry_after:.1f}s)")
        return " ".join(parts)


class LLMAuthError(LLMProviderError):
    """Authentication or authorization failure (e.g. invalid or revoked API key)."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        status_code: int = 401,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            error_type=LLMErrorType.AUTH_FAILED,
            status_code=status_code,
            retryable=False,
            details=details,
        )


class LLMConfigError(LLMProviderError):
    """Configuration error (e.g. missing API key, unsupported provider)."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            error_type=LLMErrorType.INVALID_CONFIGURATION,
            status_code=None,
            retryable=False,
            details=details,
        )


class LLMRateLimitError(LLMProviderError):
    """Transient request rate limit exceeded (e.g. requests per minute limit)."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        retry_after: float | None = None,
        status_code: int = 429,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            error_type=LLMErrorType.RATE_LIMITED,
            status_code=status_code,
            retryable=True,
            retry_after=retry_after,
            details=details,
        )


class LLMQuotaExhaustedError(LLMProviderError):
    """Daily or billing quota exhausted (e.g. free-tier daily requests exceeded)."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        retry_after: float | None = None,
        status_code: int = 429,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            error_type=LLMErrorType.QUOTA_EXHAUSTED,
            status_code=status_code,
            retryable=False,  # Quota is exhausted for the day/billing cycle; do not endlessly retry
            retry_after=retry_after,
            details=details,
        )


class LLMNetworkError(LLMProviderError):
    """Network connection, DNS, or socket transport failure."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            error_type=LLMErrorType.NETWORK_ERROR,
            status_code=None,
            retryable=True,
            details=details,
        )


class LLMTimeoutError(LLMProviderError):
    """Provider request timed out."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            error_type=LLMErrorType.TIMEOUT,
            status_code=408,
            retryable=True,
            details=details,
        )


class LLMServiceUnavailableError(LLMProviderError):
    """Upstream LLM service unavailable or experiencing outages (HTTP 500, 502, 503, 504)."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        status_code: int = 503,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            error_type=LLMErrorType.SERVICE_UNAVAILABLE,
            status_code=status_code,
            retryable=True,
            details=details,
        )


class LLMInvalidRequestError(LLMProviderError):
    """Malformed request or invalid arguments sent to provider (HTTP 400)."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            error_type=LLMErrorType.INVALID_REQUEST,
            status_code=status_code,
            retryable=False,
            details=details,
        )


class LLMContentPolicyError(LLMProviderError):
    """Generation blocked by provider safety or content moderation policies."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            error_type=LLMErrorType.CONTENT_POLICY_ERROR,
            status_code=None,
            retryable=False,
            details=details,
        )


class LLMModelNotFoundError(LLMProviderError):
    """Target LLM model does not exist or access is forbidden (HTTP 404)."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        status_code: int = 404,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            provider=provider,
            error_type=LLMErrorType.MODEL_NOT_FOUND,
            status_code=status_code,
            retryable=False,
            details=details,
        )
