"""
Unit tests for MemoryPolicy (Secret Filtering, Duplicate Prevention, Conflict Resolution).
"""

from src.database.connection import DatabaseManager
from src.memory.models import (
    MemoryCandidate,
    MemoryImportance,
    MemoryItem,
    MemoryPolicyDecision,
    MemorySource,
    MemoryType,
)
from src.memory.policy import MemoryPolicy
from src.memory.repository import MemoryRepository


def test_memory_policy_secret_filtering(tmp_path):
    db_mgr = DatabaseManager(db_path=tmp_path / "test.db")
    repo = MemoryRepository(db_manager=db_mgr)
    policy = MemoryPolicy(repository=repo)

    # API key candidate
    cand_api = MemoryCandidate(
        content="My API key is sk-1234567890123456789012345",
        type=MemoryType.USER_FACT,
        source=MemorySource.USER_EXPLICIT,
    )
    decision, _ = policy.evaluate(cand_api)
    assert decision == MemoryPolicyDecision.DO_NOT_STORE

    # Password candidate
    cand_pwd = MemoryCandidate(
        content="My password=SecretPassword123",
        type=MemoryType.USER_FACT,
        source=MemorySource.USER_EXPLICIT,
    )
    decision, _ = policy.evaluate(cand_pwd)
    assert decision == MemoryPolicyDecision.DO_NOT_STORE


def test_memory_policy_duplicate_prevention(tmp_path):
    db_mgr = DatabaseManager(db_path=tmp_path / "test.db")
    repo = MemoryRepository(db_manager=db_mgr)
    policy = MemoryPolicy(repository=repo)

    repo.add(MemoryItem(id=None, type=MemoryType.USER_PREFERENCE, content="I use VS Code", source=MemorySource.USER_EXPLICIT))

    cand_dup = MemoryCandidate(
        content="I use VS Code",
        type=MemoryType.USER_PREFERENCE,
        source=MemorySource.USER_EXPLICIT,
    )
    decision, _ = policy.evaluate(cand_dup)
    assert decision == MemoryPolicyDecision.DO_NOT_STORE


def test_memory_policy_conflict_resolution(tmp_path):
    db_mgr = DatabaseManager(db_path=tmp_path / "test.db")
    repo = MemoryRepository(db_manager=db_mgr)
    policy = MemoryPolicy(repository=repo)

    repo.add(MemoryItem(id=None, type=MemoryType.USER_PREFERENCE, content="Preferred editor: VS Code", source=MemorySource.USER_EXPLICIT))

    cand_new = MemoryCandidate(
        content="Preferred editor: Cursor",
        type=MemoryType.USER_PREFERENCE,
        source=MemorySource.USER_EXPLICIT,
    )
    decision, existing = policy.evaluate(cand_new)
    assert decision == MemoryPolicyDecision.UPDATE_EXISTING
    assert existing is not None
    assert existing.content == "Preferred editor: VS Code"
