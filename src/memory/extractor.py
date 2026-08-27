"""
Memory Extractor Subsystem.
Analyzes user input statements to detect explicit and candidate memory items.
"""

import re
from src.memory.models import (
    MemoryCandidate,
    MemoryImportance,
    MemorySource,
    MemoryType,
)


class MemoryExtractor:
    """Extracts explicit memory requests and preference candidates from user statements."""

    EXPLICIT_PATTERNS = [
        (r"(?:remember|keep in mind|note) that (.*)", MemoryImportance.HIGH),
        (r"remember (.*)", MemoryImportance.HIGH),
        (r"my main project is (.*)", MemoryImportance.HIGH),
        (r"i prefer (.*)", MemoryImportance.MEDIUM),
        (r"i use (.*)", MemoryImportance.MEDIUM),
        (r"i switched to (.*)", MemoryImportance.HIGH),
    ]

    def extract_candidates(self, user_statement: str) -> list[MemoryCandidate]:
        """Analyze statement and extract candidate memories."""
        statement = user_statement.strip()
        candidates: list[MemoryCandidate] = []

        # 1. Explicit Remember Statements
        for pattern, importance in self.EXPLICIT_PATTERNS:
            match = re.search(pattern, statement, re.IGNORECASE)
            if match:
                extracted_fact = match.group(1).strip().rstrip(".")
                mem_type = self._classify_type(statement, extracted_fact)

                candidates.append(
                    MemoryCandidate(
                        content=extracted_fact,
                        type=mem_type,
                        source=MemorySource.USER_EXPLICIT,
                        importance=importance,
                        confidence=0.95,
                        reason="Explicit user request",
                    )
                )
                return candidates

        return candidates

    def _classify_type(self, statement: str, fact: str) -> MemoryType:
        """Classify memory candidate type based on text content."""
        lower_fact = fact.lower()
        if "project" in lower_fact or "astra" in lower_fact:
            return MemoryType.PROJECT
        elif "prefer" in lower_fact or "editor" in lower_fact or "use" in lower_fact:
            return MemoryType.USER_PREFERENCE
        elif "workflow" in lower_fact or "folder" in lower_fact:
            return MemoryType.WORKFLOW
        elif "task" in lower_fact:
            return MemoryType.TASK
        else:
            return MemoryType.USER_FACT
