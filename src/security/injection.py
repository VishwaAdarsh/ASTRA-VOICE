"""
Prompt Injection Defense Component.
Sanitizes external data payloads (web pages, OCR text, file contents, memory data, tool output) to prevent prompt injection hijacks.
"""

import re
from src.core.config import Config
from src.core.logger import get_logger
from src.security.auditor import SecurityAuditor

logger = get_logger()


class PromptInjectionDefense:
    """Sanitizes untrusted data inputs to prevent LLM prompt injection and instruction override."""

    INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(previous|all)\s+instructions", re.IGNORECASE),
        re.compile(r"system\s+prompt\s+override", re.IGNORECASE),
        re.compile(r"delete\s+all\s+files", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+a", re.IGNORECASE),
        re.compile(r"bypass\s+security", re.IGNORECASE),
        re.compile(r"disable\s+confirmation", re.IGNORECASE),
    ]

    def __init__(self, config: Config | None = None, auditor: SecurityAuditor | None = None):
        self.config = config or Config()
        self.auditor = auditor or SecurityAuditor(config=self.config)

    def sanitize_untrusted_data(self, content: str, source_tag: str = "UNTRUSTED DATA") -> str:
        """Wrap and sanitize untrusted data to enforce instruction/data separation."""
        if not content:
            return ""

        # Check for injection patterns
        detected = False
        for pattern in self.INJECTION_PATTERNS:
            if pattern.search(content):
                detected = True
                self.auditor.record_event(
                    event_type="PROMPT_INJECTION_ATTEMPT",
                    component="PromptInjectionDefense",
                    message=f"Prompt injection pattern detected from source '{source_tag}'.",
                    severity="HIGH",
                )
                break

        # Wrap in strict XML data boundary tag to enforce data boundary
        clean_text = content.replace("</untrusted_data>", "[TAG_REDACTED]")
        return f"<{source_tag}>\n{clean_text}\n</{source_tag}>"
