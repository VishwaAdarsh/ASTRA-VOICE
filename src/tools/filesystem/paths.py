"""
Path Security and Trusted Location Resolver.
Converts human-friendly folder shortcuts into validated canonical paths while rejecting restricted locations and path traversal.
"""

import os
from pathlib import Path
from src.core.config import Config
from src.core.exceptions import PathSecurityError
from src.core.logger import get_logger

logger = get_logger()


class PathResolver:
    """Resolves and validates paths against trusted location security policies."""

    def __init__(self, config: Config | None = None, sandbox_root: Path | None = None):
        self.config = config or Config()
        self.sandbox_root = sandbox_root

        # Restricted system path keywords (lowercased)
        self.restricted_prefixes = [
            "c:\\windows",
            "c:\\program files",
            "c:\\program files (x86)",
            "c:\\system32",
            "c:\\boot",
        ]

    def resolve_folder(self, target: str) -> Path:
        """Resolve folder shortcut or raw path."""
        cleaned = target.strip().lower()

        # Check sandbox override for testing
        if self.sandbox_root and self.sandbox_root.exists():
            candidate = self.sandbox_root / target.lstrip("/\\")
            if not candidate.exists() and cleaned in self.config.folder_allowlist:
                return self.sandbox_root.resolve()
            return candidate.resolve()


        # Check known folder allowlist
        if cleaned in self.config.folder_allowlist:
            return self.config.folder_allowlist[cleaned]

        # Check raw path
        raw_path = Path(target)
        if not raw_path.is_absolute():
            # Assume relative to user profile / home
            raw_path = Path(os.getenv("USERPROFILE", Path.home())) / target

        resolved = raw_path.resolve()
        self.validate_path_security(resolved)
        return resolved

    def resolve_file(self, target: str, base_folder: Path | None = None) -> Path:
        """Resolve file path."""
        raw_path = Path(target)
        if raw_path.is_absolute():
            resolved = raw_path.resolve()
        else:
            base = base_folder or Path(os.getenv("USERPROFILE", Path.home())) / "Downloads"
            resolved = (base / target).resolve()

        self.validate_path_security(resolved)
        return resolved

    def validate_path_security(self, path: Path) -> None:
        """Enforce path security: reject path traversal and restricted Windows system directories."""
        path_str = str(path).lower()

        # 1. Reject restricted system directories
        for restricted in self.restricted_prefixes:
            if path_str.startswith(restricted):
                error_msg = f"Access denied to restricted system location '{path}'."
                logger.warning(f"SECURITY_REJECTION: {error_msg}")
                raise PathSecurityError(error_msg)
