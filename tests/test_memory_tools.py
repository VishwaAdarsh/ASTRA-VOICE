"""
Integration tests for Phase 7 Memory Tools (RememberTool, RetrieveMemoryTool, ForgetMemoryTool, ListMemoriesTool).
"""

from src.brain.models import ExecutionStatus, PermissionLevel
from src.database.connection import DatabaseManager
from src.memory.manager import MemoryManager
from src.memory.repository import MemoryRepository
from src.tools.memory.forget import ForgetMemoryTool
from src.tools.memory.list import ListMemoriesTool
from src.tools.memory.remember import RememberTool
from src.tools.memory.retrieve import RetrieveMemoryTool


def test_memory_tools_lifecycle(tmp_path):
    db_mgr = DatabaseManager(db_path=tmp_path / "test.db")
    repo = MemoryRepository(db_manager=db_mgr)
    mgr = MemoryManager(repository=repo)

    remember_tool = RememberTool(memory_manager=mgr)
    retrieve_tool = RetrieveMemoryTool(memory_manager=mgr)
    list_tool = ListMemoriesTool(memory_manager=mgr)
    forget_tool = ForgetMemoryTool(memory_manager=mgr)

    # 1. RememberTool
    res_rem = remember_tool.execute({"content": "Main project is ASTRA-VOICE", "memory_type": "PROJECT"})
    assert res_rem.status == ExecutionStatus.SUCCESS
    assert "ASTRA-VOICE" in res_rem.message
    mem_id = res_rem.data["id"]

    # 2. RetrieveMemoryTool
    res_ret = retrieve_tool.execute({"query": "ASTRA-VOICE"})
    assert res_ret.status == ExecutionStatus.SUCCESS
    assert res_ret.data["count"] == 1

    # 3. ListMemoriesTool
    res_list = list_tool.execute({})
    assert res_list.status == ExecutionStatus.SUCCESS
    assert res_list.data["count"] == 1

    # 4. ForgetMemoryTool
    res_for = forget_tool.execute({"memory_id": mem_id})
    assert res_for.status == ExecutionStatus.SUCCESS

    # Verify cleared
    res_list_after = list_tool.execute({})
    assert res_list_after.data["count"] == 0
