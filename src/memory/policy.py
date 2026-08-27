"""
Memory Policy Engine.
Evaluates memory candidates, enforces secret filtering, duplicate prevention, and preference conflict updates.
"""

import re
from src.core.exceptions import SecretFilteringError
from src.core.logger import get_logger
from src.memory.models import (
    MemoryCandidate,
    MemoryItem,
    MemoryPolicyDecision,
    MemorySource,
    MemoryType,
)
from src.memory.repository import MemoryRepository

logger = get_logger()


class MemoryPolicy:
    """Evaluates candidate memories against privacy rules, duplicate checks, and conflict resolution."""

    SECRET_PATTERNS = [
        r"sk-[a-zA-Z0-9]{20,}",  # OpenAI API key pattern
        r"ghp_[a-zA-Z0-9]{30,}",  # GitHub Personal Access Token
        r"bearer\s+[a-zA-Z0-9\-_\.=]+",  # Bearer tokens
        r"(?:password|passwd|pwd)\s*[:=]\s*\S+",  # Passwords
        r"(?:api_key|apikey|secret_key)\s*[:=]\s*\S+",  # Generic API keys
        r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",  # Credit Card numbers
    ]

    def __init__(self, repository: MemoryRepository | None = None):
        self.repository = repository

    def evaluate(self, candidate: MemoryCandidate) -> tuple[MemoryPolicyDecision, MemoryItem | None]:
        """Evaluate candidate memory and return policy decision with matching existing item if updating."""
        # 1. Privacy & Secret Filtering
        if self._contains_secrets(candidate.content):
            logger.warning(f"MemoryPolicy: Candidate blocked due to secret credential filter: '{candidate.content}'")
            return MemoryPolicyDecision.DO_NOT_STORE, None

        if not candidate.content or len(candidate.content.strip()) < 3:
            return MemoryPolicyDecision.DO_NOT_STORE, None

        if not self.repository:
            return MemoryPolicyDecision.STORE, None

        # 2. Check for Duplicate Records
        existing_items = self.repository.search(query="", memory_type=candidate.type)
        candidate_clean = candidate.content.lower().strip()

        for item in existing_items:
            item_clean = item.content.lower().strip()
            if candidate_clean == item_clean:
                logger.info(f"MemoryPolicy: Duplicate active memory detected. Skipping store for '{candidate.content}'")
                return MemoryPolicyDecision.DO_NOT_STORE, None

            # 3. Conflict Resolution (e.g. Preference / Project updates)
            if self._is_conflict(candidate, item):
                logger.info(f"MemoryPolicy: Conflict detected between new '{candidate.content}' and existing #{item.id} '{item.content}'. Updating existing.")
                return MemoryPolicyDecision.UPDATE_EXISTING, item

        return MemoryPolicyDecision.STORE, None

    def _contains_secrets(self, content: str) -> bool:
        """Check text against secret regex patterns."""
        for pattern in self.SECRET_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False

    def _is_conflict(self, candidate: MemoryCandidate, existing: MemoryItem) -> bool:
        """Determine if a new candidate conflicts with an existing stored preference/fact."""
        c_text = candidate.content.lower()
        e_text = existing.content.lower()

        # Preferred editor conflict
        if ("editor" in c_text or "ide" in c_text) and ("editor" in e_text or "ide" in e_text):
            return True

        # Main project conflict
        if "main project" in c_text and "main project" in e_text:
            return True

        # Preferred UI framework conflict
        if ("ui framework" in c_text or "gui" in c_text) and ("ui framework" in e_text or "gui" in e_text):
            return True

        return False
