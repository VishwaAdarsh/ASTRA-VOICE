"""
Automation Repository Database Storage Layer.
Provides SQLite persistence for automations, runs, and notifications.
"""

import json
from src.core.config import Config
from src.core.logger import get_logger
from src.database.connection import DatabaseManager
from src.automation.models import (
    ActionType,
    Automation,
    AutomationAction,
    AutomationRun,
    AutomationStatus,
    Condition,
    ConditionType,
    Notification,
    NotificationPriority,
    RunStatus,
    TriggerType,
)

logger = get_logger()


class AutomationRepository:
    """SQLite Persistence Layer for Automations, Runs, and Notifications."""

    def __init__(self, config: Config | None = None, db_manager: DatabaseManager | None = None):
        self.config = config or Config()
        self.db = db_manager or DatabaseManager(config=self.config)

    def save_automation(self, auto: Automation) -> None:
        """Insert or update an automation record."""
        sql = """
        INSERT INTO automations (
            id, name, description, status, trigger_type, trigger_config, condition_config, action_config,
            permissions, created_at, updated_at, last_run_at, next_run_at, run_count, failure_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            description=excluded.description,
            status=excluded.status,
            trigger_config=excluded.trigger_config,
            condition_config=excluded.condition_config,
            action_config=excluded.action_config,
            permissions=excluded.permissions,
            updated_at=excluded.updated_at,
            last_run_at=excluded.last_run_at,
            next_run_at=excluded.next_run_at,
            run_count=excluded.run_count,
            failure_count=excluded.failure_count;
        """
        cond_dict = {"type": auto.condition.type.value, "parameters": auto.condition.parameters} if auto.condition else {}
        action_dict = {"type": auto.action.type.value, "tool": auto.action.tool, "arguments": auto.action.arguments} if auto.action else {}

        with self.db.get_connection() as conn:
            conn.execute(
                sql,
                (
                    auto.id,
                    auto.name,
                    auto.description,
                    auto.status.value,
                    auto.trigger_type.value,
                    json.dumps(auto.trigger_config),
                    json.dumps(cond_dict),
                    json.dumps(action_dict),
                    ",".join(auto.permissions),
                    auto.created_at,
                    auto.updated_at,
                    auto.last_run_at,
                    auto.next_run_at,
                    auto.run_count,
                    auto.failure_count,
                ),
            )

    def get_automation(self, auto_id: str) -> Automation | None:
        """Retrieve automation by ID."""
        sql = "SELECT * FROM automations WHERE id = ?;"
        with self.db.get_connection() as conn:
            row = conn.execute(sql, (auto_id,)).fetchone()
            if not row:
                return None

            cond_dict = json.loads(row["condition_config"] or "{}")
            cond = Condition(type=ConditionType(cond_dict["type"]), parameters=cond_dict.get("parameters", {})) if cond_dict and "type" in cond_dict else None

            act_dict = json.loads(row["action_config"] or "{}")
            act = AutomationAction(type=ActionType(act_dict["type"]), tool=act_dict.get("tool", "system_info"), arguments=act_dict.get("arguments", {})) if act_dict and "type" in act_dict else None

            perms = [p for p in (row["permissions"] or "").split(",") if p]

            return Automation(
                id=row["id"],
                name=row["name"],
                description=row["description"] or "",
                status=AutomationStatus(row["status"]),
                trigger_type=TriggerType(row["trigger_type"]),
                trigger_config=json.loads(row["trigger_config"] or "{}"),
                condition=cond,
                action=act,
                permissions=perms,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                last_run_at=row["last_run_at"],
                next_run_at=row["next_run_at"],
                run_count=row["run_count"] or 0,
                failure_count=row["failure_count"] or 0,
            )

    def delete_automation(self, auto_id: str) -> bool:
        """Delete automation by ID."""
        sql = "DELETE FROM automations WHERE id = ?;"
        with self.db.get_connection() as conn:
            cur = conn.execute(sql, (auto_id,))
            return cur.rowcount > 0

    def list_automations(self, status: AutomationStatus | None = None) -> list[Automation]:
        """List automations optionally filtered by status."""
        if status:
            sql = "SELECT id FROM automations WHERE status = ? ORDER BY created_at DESC;"
            args = (status.value,)
        else:
            sql = "SELECT id FROM automations ORDER BY created_at DESC;"
            args = ()

        results = []
        with self.db.get_connection() as conn:
            rows = conn.execute(sql, args).fetchall()
            for r in rows:
                a = self.get_automation(r["id"])
                if a:
                    results.append(a)
        return results

    def save_run(self, run: AutomationRun) -> int:
        """Save or update an automation execution run log."""
        sql = """
        INSERT INTO automation_runs (automation_id, started_at, completed_at, status, result_summary, error_message)
        VALUES (?, ?, ?, ?, ?, ?);
        """
        with self.db.get_connection() as conn:
            cur = conn.execute(
                sql,
                (
                    run.automation_id,
                    run.started_at,
                    run.completed_at,
                    run.status.value,
                    run.result_summary,
                    run.error_message,
                ),
            )
            run.id = cur.lastrowid
            return run.id or 0

    def save_notification(self, notif: Notification) -> None:
        """Save a user notification."""
        sql = """
        INSERT INTO notifications (id, type, title, message, priority, source_automation_id, created_at, read_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET read_at=excluded.read_at, status=excluded.status;
        """
        with self.db.get_connection() as conn:
            conn.execute(
                sql,
                (
                    notif.id,
                    notif.type,
                    notif.title,
                    notif.message,
                    notif.priority.value,
                    notif.source_automation_id,
                    notif.created_at,
                    notif.read_at,
                    notif.status,
                ),
            )

    def list_notifications(self, unread_only: bool = False, limit: int = 20) -> list[Notification]:
        """Retrieve recent user notifications."""
        if unread_only:
            sql = "SELECT * FROM notifications WHERE status = 'UNREAD' ORDER BY created_at DESC LIMIT ?;"
            args = (limit,)
        else:
            sql = "SELECT * FROM notifications ORDER BY created_at DESC LIMIT ?;"
            args = (limit,)

        notifications = []
        with self.db.get_connection() as conn:
            rows = conn.execute(sql, args).fetchall()
            for r in rows:
                notifications.append(
                    Notification(
                        id=r["id"],
                        type=r["type"],
                        title=r["title"],
                        message=r["message"],
                        priority=NotificationPriority(r["priority"]),
                        source_automation_id=r["source_automation_id"],
                        created_at=r["created_at"],
                        read_at=r["read_at"],
                        status=r["status"],
                    )
                )
        return notifications
