"""
Task Repository Database Storage Layer.
Provides SQLite persistence for tasks, steps, checkpoints, and execution events.
"""

import json
from src.core.config import Config
from src.core.logger import get_logger
from src.database.connection import DatabaseManager
from src.task.models import (
    ActionRiskLevel,
    AutonomyLevel,
    StepStatus,
    Task,
    TaskCheckpoint,
    TaskPlan,
    TaskStatus,
    TaskStep,
)

logger = get_logger()


class TaskRepository:
    """SQLite Persistence Layer for Autonomous Tasks and Execution Logs."""

    def __init__(self, config: Config | None = None, db_manager: DatabaseManager | None = None):
        self.config = config or Config()
        self.db = db_manager or DatabaseManager(config=self.config)

    def save_task(self, task: Task) -> None:
        """Insert or update a task record."""
        sql = """
        INSERT INTO tasks (id, goal, status, autonomy_level, created_at, started_at, completed_at, result_summary, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            status=excluded.status,
            started_at=excluded.started_at,
            completed_at=excluded.completed_at,
            result_summary=excluded.result_summary,
            error_message=excluded.error_message;
        """
        with self.db.get_connection() as conn:
            conn.execute(
                sql,
                (
                    task.id,
                    task.goal,
                    task.status.value,
                    task.autonomy_level.value,
                    task.created_at,
                    task.started_at,
                    task.completed_at,
                    task.result_summary,
                    task.error_message,
                ),
            )

        if task.plan and task.plan.steps:
            self.save_steps(task.id, task.plan.steps)

    def save_steps(self, task_id: str, steps: list[TaskStep]) -> None:
        """Insert or update step records for a task."""
        sql = """
        INSERT INTO task_steps (task_id, step_number, description, tool_name, arguments, expected_result, status, result_data, error_message, started_at, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM task_steps WHERE task_id = ?;", (task_id,))
            for step in steps:
                conn.execute(
                    sql,
                    (
                        task_id,
                        step.step_number,
                        step.description,
                        step.tool_name,
                        json.dumps(step.arguments),
                        step.expected_result,
                        step.status.value,
                        json.dumps(step.result_data),
                        step.error_message,
                        step.started_at,
                        step.completed_at,
                    ),
                )

    def get_task(self, task_id: str) -> Task | None:
        """Retrieve task by ID including plan steps."""
        sql = "SELECT * FROM tasks WHERE id = ?;"
        with self.db.get_connection() as conn:
            row = conn.execute(sql, (task_id,)).fetchone()
            if not row:
                return None

            steps = self.get_steps(task_id)
            plan = TaskPlan(goal=row["goal"], steps=steps) if steps else None

            return Task(
                id=row["id"],
                goal=row["goal"],
                status=TaskStatus(row["status"]),
                autonomy_level=AutonomyLevel(row["autonomy_level"]),
                plan=plan,
                created_at=row["created_at"],
                started_at=row["started_at"],
                completed_at=row["completed_at"],
                result_summary=row["result_summary"] or "",
                error_message=row["error_message"] or "",
            )

    def get_steps(self, task_id: str) -> list[TaskStep]:
        """Retrieve step records for a task."""
        sql = "SELECT * FROM task_steps WHERE task_id = ? ORDER BY step_number ASC;"
        steps = []
        with self.db.get_connection() as conn:
            rows = conn.execute(sql, (task_id,)).fetchall()
            for r in rows:
                steps.append(
                    TaskStep(
                        step_number=r["step_number"],
                        description=r["description"],
                        tool_name=r["tool_name"],
                        arguments=json.loads(r["arguments"] or "{}"),
                        expected_result=r["expected_result"] or "",
                        status=StepStatus(r["status"]),
                        result_data=json.loads(r["result_data"] or "{}"),
                        error_message=r["error_message"] or "",
                        started_at=r["started_at"],
                        completed_at=r["completed_at"],
                    )
                )
        return steps

    def save_checkpoint(self, checkpoint: TaskCheckpoint) -> None:
        """Save task state snapshot checkpoint."""
        sql = """
        INSERT INTO task_checkpoints (task_id, step_number, state_json, timestamp, safe_to_resume)
        VALUES (?, ?, ?, ?, ?);
        """
        with self.db.get_connection() as conn:
            conn.execute(
                sql,
                (
                    checkpoint.task_id,
                    checkpoint.step_number,
                    checkpoint.state_json,
                    checkpoint.timestamp,
                    1 if checkpoint.safe_to_resume else 0,
                ),
            )

    def log_event(self, task_id: str, event_type: str, payload: dict | None = None) -> None:
        """Log an audit event entry for a task."""
        sql = "INSERT INTO task_events (task_id, event_type, payload_json, timestamp) VALUES (?, ?, ?, datetime('now'));"
        with self.db.get_connection() as conn:
            conn.execute(sql, (task_id, event_type, json.dumps(payload or {})))

    def list_tasks(self, limit: int = 20) -> list[Task]:
        """List recent tasks."""
        sql = "SELECT id FROM tasks ORDER BY created_at DESC LIMIT ?;"
        tasks = []
        with self.db.get_connection() as conn:
            rows = conn.execute(sql, (limit,)).fetchall()
            for r in rows:
                t = self.get_task(r["id"])
                if t:
                    tasks.append(t)
        return tasks
