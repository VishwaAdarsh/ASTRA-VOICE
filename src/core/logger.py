"""
Centralized logging system for ASTRA.
Formats and records log messages both to the console and to data/logs/astra.log with secret redaction and rotation.
"""

import logging
from logging.handlers import RotatingFileHandler
import re
import sys
from pathlib import Path

_logger_initialized = False


class SecretRedactionFilter(logging.Filter):
    """Logging filter to redact API keys, bearer tokens, and secrets from log entries."""

    SECRET_PATTERNS = [
        re.compile(r"(api[_-]?key[\"'\s:=]+)([a-zA-Z0-9_\-\.]{8,})", re.IGNORECASE),
        re.compile(r"(\bkey[\"'\s:=]+)([a-zA-Z0-9_\-\.]{8,})", re.IGNORECASE),
        re.compile(r"(sk[_-][a-zA-Z0-9_\-\.]{8,})", re.IGNORECASE),
        re.compile(r"(AQ\.[a-zA-Z0-9_\-]{8,})", re.IGNORECASE),
        re.compile(r"(bearer\s+)([a-zA-Z0-9_\-\.]{8,})", re.IGNORECASE),
        re.compile(r"(password[\"'\s:=]+)([^\s\"']+)", re.IGNORECASE),
        re.compile(r"(token[\"'\s:=]+)([a-zA-Z0-9_\-\.]{8,})", re.IGNORECASE),
    ]


    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.redact(record.msg)
        return True

    @classmethod
    def redact(cls, text: str) -> str:
        """Redact sensitive credentials in text string."""
        for pattern in cls.SECRET_PATTERNS:
            if pattern.groups == 2:
                text = pattern.sub(r"\1[REDACTED]", text)
            else:
                text = pattern.sub(r"[REDACTED]", text)
        return text



def setup_logger(log_file: Path | str | None = None, log_level: str = "INFO") -> logging.Logger:
    """Set up and configure the root ASTRA logger with secret redaction and file rotation."""
    global _logger_initialized

    logger = logging.getLogger("ASTRA")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Avoid adding duplicate handlers if logger already initialized
    if _logger_initialized and logger.handlers:
        return logger

    logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    redaction_filter = SecretRedactionFilter()

    # Console Handler (StreamHandler)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(redaction_filter)
    console_handler.setLevel(logging.WARNING)  # Clean CLI interface
    logger.addHandler(console_handler)

    # File Handler with Rotation
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.addFilter(redaction_filter)
        file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        logger.addHandler(file_handler)

    _logger_initialized = True
    return logger


def get_logger() -> logging.Logger:
    """Get the initialized ASTRA logger instance."""
    logger = logging.getLogger("ASTRA")
    if not logger.handlers:
        setup_logger()
    return logger
