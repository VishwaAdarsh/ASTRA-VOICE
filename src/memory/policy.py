"""
Memory Policy Engine (Memory V2).
Evaluates memory candidates, enforces secret filtering, duplicate prevention,
write policy rules, and preference conflict resolution.
"""

import re
from typing import Optional
from src.core.logger import get_logger
from src.memory.models import (
    MemoryCandidate,
    MemoryItem,
    MemoryPolicyDecision,
    MemorySource,
    MemoryStatus,
    MemoryType,
)
from src.memory.repository import MemoryRepository
from src.security.auditor import SecretRedactionFilter

logger = get_logger()


class MemoryPolicy:
    """Evaluates candidate memories against privacy rules, duplicate checks, and conflict resolution."""

    SECRET_PATTERNS = [
        re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE),  # OpenAI API key pattern
        re.compile(r"ghp_[a-zA-Z0-9]{30,}", re.IGNORECASE),  # GitHub Personal Access Token
        re.compile(r"bearer\s+[a-zA-Z0-9\-_\.=]+", re.IGNORECASE),  # Bearer tokens
        re.compile(r"(?:password|passwd|pwd)\s*[:=]\s*\S+", re.IGNORECASE),  # Passwords
        re.compile(r"(?:api_key|apikey|secret_key)\s*[:=]\s*\S+", re.IGNORECASE),  # Generic API keys
        re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"),  # Credit Card numbers
        re.compile(r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----", re.IGNORECASE),  # Private keys
    ]

    NOISE_PATTERNS = [
        re.compile(r"^(?:hi|hello|hey|greetings|good morning|good evening|good afternoon|thanks|thank you|ok|okay|cool|bye|goodbye)\b", re.IGNORECASE),
        re.compile(r"^(?:what|where|who|when|why|how)\s+(?:is|are|do|does|can|will|should)\b", re.IGNORECASE),
    ]

    def __init__(self, repository: Optional[MemoryRepository] = None, config: Optional[Any] = None):
        self.repository = repository
        self.config = config

    def evaluate(self, candidate: MemoryCandidate) -> tuple[MemoryPolicyDecision, Optional[MemoryItem]]:
        """
        Evaluate candidate memory against privacy, noise, duplicates, and conflicts.
        
        Returns:
            Tuple of (MemoryPolicyDecision, matching_existing_item_or_None)
        """
        # 1. Privacy & Secret Filtering
        if self._contains_secrets(candidate.content):
            logger.warning(f"MemoryPolicy: Candidate blocked due to secret credential filter: '{candidate.content}'")
            return MemoryPolicyDecision.DO_NOT_STORE, None

        # 2. Noise & Length Filter
        content_clean = candidate.content.strip()
        if not content_clean or len(content_clean) < 3:
            logger.debug(f"MemoryPolicy: Candidate rejected due to insufficient length: '{content_clean}'")
            return MemoryPolicyDecision.DO_NOT_STORE, None

        # Check if text is conversational noise or temporary question (unless explicitly instructed to remember)
        if candidate.source != MemorySource.USER_EXPLICIT and self._is_noise(content_clean):
            logger.debug(f"MemoryPolicy: Candidate rejected as conversational noise: '{content_clean}'")
            return MemoryPolicyDecision.DO_NOT_STORE, None

        if not self.repository:
            return MemoryPolicyDecision.STORE, None

        # 3. Check for Duplicate Records
        # Search active memories of the same or compatible type
        existing_items = self.repository.list_all(status=MemoryStatus.ACTIVE)
        candidate_norm = self._normalize_content(content_clean)

        for item in existing_items:
            item_norm = self._normalize_content(item.content)
            
            # Exact or highly normalized match
            if candidate_norm == item_norm and (
                item.type == candidate.type or item.project_id == candidate.project_id
            ):
                logger.info(f"MemoryPolicy: Duplicate active memory detected. Skipping store for '{candidate.content}'")
                return MemoryPolicyDecision.DO_NOT_STORE, item

            # 4. Conflict Resolution (e.g. Preference / Project updates)
            if self._is_conflict(candidate, item):
                logger.info(
                    f"MemoryPolicy: Conflict detected between new '{candidate.content}' and existing #{item.id or item.memory_id} '{item.content}'. "
                    "Decided: UPDATE_EXISTING"
                )
                return MemoryPolicyDecision.UPDATE_EXISTING, item

        return MemoryPolicyDecision.STORE, None

    def detect_conflicts(self, candidate: MemoryCandidate, existing_items: list[MemoryItem]) -> list[MemoryItem]:
        """Detect and return any existing memories that conflict with the candidate."""
        return [item for item in existing_items if self._is_conflict(candidate, item)]

    def _contains_secrets(self, content: str) -> bool:
        """Check text against secret regex patterns and SecretRedactionFilter."""
        # 1. Centralized SecretRedactionFilter check
        redacted = SecretRedactionFilter.redact(content)
        if redacted != content:
            return True

        # 2. Explicit regex patterns
        for pattern in self.SECRET_PATTERNS:
            if pattern.search(content):
                return True
        return False

    def _is_noise(self, content: str) -> bool:
        """Check if content represents greeting, short question, or temporary noise."""
        for pattern in self.NOISE_PATTERNS:
            if pattern.search(content):
                return True
        return False

    def _normalize_content(self, text: str) -> str:
        """Normalize text for deterministic duplicate matching."""
        cleaned = text.lower().strip().rstrip(".")
        cleaned = re.sub(r"^(?:remember\s+(?:that\s+)?|i\s+prefer\s+|i\s+use\s+)", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned

    def _is_conflict(self, candidate: MemoryCandidate, existing: MemoryItem) -> bool:
        """Determine if a new candidate conflicts with an existing stored preference or fact."""
        c_text = candidate.content.lower()
        e_text = existing.content.lower()

        # Preferred editor / IDE conflict
        if ("editor" in c_text or "ide" in c_text) and ("editor" in e_text or "ide" in e_text):
            return True

        # Main project conflict
        if "main project" in c_text and "main project" in e_text:
            return True

        # Preferred UI framework conflict
        if ("ui framework" in c_text or "gui" in c_text) and ("ui framework" in e_text or "gui" in e_text):
            return True

        # Theme preference conflict (dark mode vs light mode)
        if ("dark mode" in c_text or "dark theme" in c_text) and ("light mode" in e_text or "light theme" in e_text):
            return True
        if ("light mode" in c_text or "light theme" in c_text) and ("dark mode" in e_text or "dark theme" in e_text):
            return True

        # Language preference conflict
        if "preferred language" in c_text and "preferred language" in e_text:
            return True

        return False
