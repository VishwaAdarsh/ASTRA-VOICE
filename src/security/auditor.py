"""
Security Auditor Component.
Records structured security events (permission denied, tool rejected, prompt injection attempts) without logging secrets.
"""

from dataclasses import dataclass, field
from datetime import datetime
from src.core.config import Config
from src.core.logger import get_logger, SecretRedactionFilter

logger = get_logger()


@dataclass
class SecurityEvent:
    """Dataclass representing a security audit log event."""

    event_type: str
    component: str
    message: str
    severity: str = "WARNING"
    details: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class SecurityAuditor:
    """Audit logger for security policy violations, permission checks, and threat events."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.audit_log: list[SecurityEvent] = []

    def record_event(self, event_type: str, component: str, message: str, severity: str = "WARNING", details: dict | None = None) -> SecurityEvent:
        """Record and log a security audit event with automatic secret redaction."""
        clean_msg = SecretRedactionFilter.redact(message)
        event = SecurityEvent(
            event_type=event_type,
            component=component,
            message=clean_msg,
            severity=severity,
            details=details or {},
        )
        self.audit_log.append(event)
        logger.warning(f"SECURITY_AUDIT [{event_type}] ({component}): {clean_msg}")
        return event

    def list_events(self, limit: int = 50) -> list[SecurityEvent]:
        """Get recent recorded security audit events."""
        return self.audit_log[-limit:]
