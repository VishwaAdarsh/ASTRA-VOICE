"""
Unit tests for TaskRepository and database persistence.
"""

from src.database.connection import DatabaseManager
from src.task.models import ActionRiskLevel, StepStatus, Task, TaskCheckpoint, TaskPlan, TaskStatus, TaskStep
from src.task.repository import TaskRepository


def test_task_repository_save_and_get(tmp_path):
    db_file = tmp_path / "test_tasks.db"
    db_mgr = DatabaseManager(db_path=db_file)
    repo = TaskRepository(db_manager=db_mgr)

    step1 = TaskStep(
        step_number=1,
        description="Search files",
        tool_name="search_files",
        arguments={"query": "report"},
        expected_result="File list",
        status=StepStatus.COMPLETED,
    )
    plan = TaskPlan(goal="Find report", steps=[step1])

    task = Task(
        id="task_123",
        goal="Find report",
        status=TaskStatus.COMPLETED,
        plan=plan,
        result_summary="Completed successfully",
    )

    repo.save_task(task)
    retrieved = repo.get_task("task_123")

    assert retrieved is not None
    assert retrieved.id == "task_123"
    assert retrieved.goal == "Find report"
    assert retrieved.status == TaskStatus.COMPLETED
    assert retrieved.plan is not None
    assert len(retrieved.plan.steps) == 1
    assert retrieved.plan.steps[0].tool_name == "search_files"


def test_task_repository_checkpoint(tmp_path):
    db_file = tmp_path / "test_tasks.db"
    db_mgr = DatabaseManager(db_path=db_file)
    repo = TaskRepository(db_manager=db_mgr)

    task = Task(id="task_123", goal="Find report", status=TaskStatus.COMPLETED)
    repo.save_task(task)

    cp = TaskCheckpoint(task_id="task_123", step_number=1, state_json='{"step": 1}', safe_to_resume=True)
    repo.save_checkpoint(cp)
    repo.log_event("task_123", "TASK_TEST_EVENT", {"info": "test"})

    tasks = repo.list_tasks()
    assert isinstance(tasks, list)

