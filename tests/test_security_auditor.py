"""
Unit tests for SecurityAuditor and secret redaction.
"""

from src.core.logger import SecretRedactionFilter
from src.security.auditor import SecurityAuditor


def test_secret_redaction_filter():
    raw_log = "API_KEY=sk_test_1234567890abcdef Authorization: Bearer secret_token_xyz_987"
    clean_log = SecretRedactionFilter.redact(raw_log)

    assert "sk_test" not in clean_log
    assert "secret_token" not in clean_log
    assert "[REDACTED]" in clean_log


def test_security_auditor_record_event():
    auditor = SecurityAuditor()
    event = auditor.record_event(
        event_type="PERMISSION_DENIED",
        component="ToolExecutor",
        message="User denied permission with key=sk_9999999999",
        severity="WARNING",
    )

    assert event.event_type == "PERMISSION_DENIED"
    assert "sk_9999999999" not in event.message
    assert "[REDACTED]" in event.message
    assert len(auditor.list_events()) == 1
