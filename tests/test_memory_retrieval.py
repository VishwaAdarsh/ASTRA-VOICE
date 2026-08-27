"""
Unit tests for MemoryExtractor, MemoryRetriever, and MemoryManager.
"""

from src.database.connection import DatabaseManager
from src.memory.extractor import MemoryExtractor
from src.memory.manager import MemoryManager
from src.memory.models import MemoryImportance, MemoryItem, MemorySource, MemoryType
from src.memory.repository import MemoryRepository
from src.memory.retriever import MemoryRetriever


def test_memory_extractor_explicit_patterns():
    extractor = MemoryExtractor()
    candidates = extractor.extract_candidates("Remember that my main project is ASTRA")

    assert len(candidates) == 1
    assert candidates[0].content == "my main project is ASTRA"
    assert candidates[0].type == MemoryType.PROJECT


def test_memory_manager_end_to_end(tmp_path):
    db_mgr = DatabaseManager(db_path=tmp_path / "test.db")
    repo = MemoryRepository(db_manager=db_mgr)
    mgr = MemoryManager(repository=repo)

    # 1. Extract and Remember
    items = mgr.extract_and_remember("Remember that I prefer PySide6 for GUI")
    assert len(items) == 1
    assert items[0].content == "I prefer PySide6 for GUI"

    # 2. Retrieve
    retrieved = mgr.retrieve("PySide6")
    assert len(retrieved) == 1
    assert "PySide6" in retrieved[0].memory.content

    # 3. List & Stats
    stats = mgr.get_stats()
    assert stats["total"] == 1

    # 4. Forget
    assert mgr.forget(items[0].id)
    assert len(mgr.list_all()) == 0
