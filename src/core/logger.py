"""
Centralized logging system for ASTRA.
Formats and records log messages both to the console and to data/logs/astra.log.
"""

import logging
import sys
from pathlib import Path

_logger_initialized = False


def setup_logger(log_file: Path | str | None = None, log_level: str = "INFO") -> logging.Logger:
    """Set up and configure the root ASTRA logger."""
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

    # Console Handler (StreamHandler)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.WARNING)  # CLI user interface clean, show warnings/errors only on console
    logger.addHandler(console_handler)

    # File Handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
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
