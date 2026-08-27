"""
Unit tests for TaskExecutor and TaskManager.
"""

from src.core.config import Config
from src.database.connection import DatabaseManager
from src.task.manager import TaskManager
from src.task.models import TaskStatus
from src.task.repository import TaskRepository
from src.tools.filesystem import CreateTextFileTool, FileMetadataTool, OpenFileTool, SearchFilesTool
from src.tools.registry import ToolRegistry
from src.tools.system import SystemInformationTool




def test_task_manager_execute_goal(tmp_path):
    report_file = tmp_path / "README.md"
    report_file.write_text("ASTRA Test Report Content")

    cfg = Config()
    cfg.folder_allowlist["home"] = tmp_path
    cfg.folder_allowlist["documents"] = tmp_path

    db_file = tmp_path / "test_manager.db"
    db_mgr = DatabaseManager(db_path=db_file)
    repo = TaskRepository(config=cfg, db_manager=db_mgr)

    registry = ToolRegistry()
    registry.register(SearchFilesTool(config=cfg))
    registry.register(OpenFileTool(config=cfg))
    registry.register(CreateTextFileTool(config=cfg))
    registry.register(FileMetadataTool(config=cfg))
    registry.register(SystemInformationTool())

    manager = TaskManager(config=cfg, registry=registry, repository=repo)
    result = manager.create_and_execute_goal("Find my project report and summarize it")

    assert result.status == TaskStatus.COMPLETED
    assert result.completed_steps > 0
    assert "Completed all" in result.summary



def test_task_manager_emergency_stop(tmp_path):
    db_file = tmp_path / "test_manager.db"
    db_mgr = DatabaseManager(db_path=db_file)
    repo = TaskRepository(db_manager=db_mgr)

    registry = ToolRegistry()
    registry.register(SystemInformationTool())

    manager = TaskManager(registry=registry, repository=repo)
    manager.emergency_stop()

    assert manager.executor._cancel_requested == True
