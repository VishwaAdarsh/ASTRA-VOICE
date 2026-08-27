"""
Unit tests for MemoryRepository and DatabaseManager.
"""

from src.database.connection import DatabaseManager
from src.memory.models import (
    MemoryImportance,
    MemoryItem,
    MemorySource,
    MemoryStatus,
    MemoryType,
)
from src.memory.repository import MemoryRepository


def test_memory_repository_crud(tmp_path):
    db_file = tmp_path / "test_memory.db"
    db_mgr = DatabaseManager(db_path=db_file)
    repo = MemoryRepository(db_manager=db_mgr)

    # 1. Add
    item = MemoryItem(
        id=None,
        type=MemoryType.USER_PREFERENCE,
        content="User prefers PySide6",
        source=MemorySource.USER_EXPLICIT,
        importance=MemoryImportance.HIGH,
    )
    saved = repo.add(item)
    assert saved.id is not None

    # 2. Get by ID
    retrieved = repo.get_by_id(saved.id)
    assert retrieved is not None
    assert retrieved.content == "User prefers PySide6"

    # 3. Update
    retrieved.content = "User prefers PySide6 for GUI"
    updated = repo.update(retrieved)
    assert repo.get_by_id(saved.id).content == "User prefers PySide6 for GUI"

    # 4. Search
    results = repo.search(query="PySide6")
    assert len(results) == 1

    # 5. Delete (Soft)
    assert repo.delete(saved.id)
    assert repo.get_by_id(saved.id) is None


def test_memory_repository_clear_all(tmp_path):
    db_file = tmp_path / "test_memory.db"
    db_mgr = DatabaseManager(db_path=db_file)
    repo = MemoryRepository(db_manager=db_mgr)

    repo.add(MemoryItem(id=None, type=MemoryType.USER_FACT, content="Fact 1", source=MemorySource.USER_EXPLICIT))
    repo.add(MemoryItem(id=None, type=MemoryType.PROJECT, content="Project 1", source=MemorySource.USER_EXPLICIT))

    assert len(repo.list_all()) == 2
    cleared = repo.clear_all()
    assert cleared == 2
    assert len(repo.list_all()) == 0
