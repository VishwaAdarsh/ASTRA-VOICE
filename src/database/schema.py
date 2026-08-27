"""
Database Schema Definitions and Migrations.
"""

CREATE_MEMORIES_TABLE_V1 = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT NOT NULL,
    importance TEXT DEFAULT 'MEDIUM',
    confidence REAL DEFAULT 1.0,
    status TEXT DEFAULT 'ACTIVE',
    project_id TEXT DEFAULT NULL,
    tags TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_accessed_at TEXT NOT NULL,
    expires_at TEXT DEFAULT NULL,
    access_count INTEGER DEFAULT 0
);
"""

CREATE_INDEX_TYPE = "CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type);"
CREATE_INDEX_STATUS = "CREATE INDEX IF NOT EXISTS idx_memories_status ON memories(status);"
CREATE_INDEX_PROJECT = "CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project_id);"

# Task Engine Schema (Phase 9)
CREATE_TASKS_TABLE_V3 = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    goal TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'CREATED',
    autonomy_level TEXT NOT NULL DEFAULT 'LEVEL_3',
    created_at TEXT NOT NULL,
    started_at TEXT DEFAULT NULL,
    completed_at TEXT DEFAULT NULL,
    result_summary TEXT DEFAULT '',
    error_message TEXT DEFAULT ''
);
"""

CREATE_TASK_STEPS_TABLE_V3 = """
CREATE TABLE IF NOT EXISTS task_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    step_number INTEGER NOT NULL,
    description TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    arguments TEXT DEFAULT '{}',
    expected_result TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'PENDING',
    result_data TEXT DEFAULT '{}',
    error_message TEXT DEFAULT '',
    started_at TEXT DEFAULT NULL,
    completed_at TEXT DEFAULT NULL,
    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
"""

CREATE_TASK_CHECKPOINTS_TABLE_V3 = """
CREATE TABLE IF NOT EXISTS task_checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    step_number INTEGER NOT NULL,
    state_json TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    safe_to_resume INTEGER DEFAULT 1,
    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
"""

CREATE_TASK_EVENTS_TABLE_V3 = """
CREATE TABLE IF NOT EXISTS task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT DEFAULT '{}',
    timestamp TEXT NOT NULL,
    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
"""

# Proactive Personal Assistant & Automation Schema (Phase 10)
CREATE_AUTOMATIONS_TABLE_V4 = """
CREATE TABLE IF NOT EXISTS automations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    trigger_type TEXT NOT NULL,
    trigger_config TEXT DEFAULT '{}',
    condition_config TEXT DEFAULT '{}',
    action_config TEXT DEFAULT '{}',
    permissions TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_run_at TEXT DEFAULT NULL,
    next_run_at TEXT DEFAULT NULL,
    run_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0
);
"""

CREATE_AUTOMATION_RUNS_TABLE_V4 = """
CREATE TABLE IF NOT EXISTS automation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    automation_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT DEFAULT NULL,
    status TEXT NOT NULL DEFAULT 'STARTED',
    result_summary TEXT DEFAULT '',
    error_message TEXT DEFAULT '',
    FOREIGN KEY(automation_id) REFERENCES automations(id) ON DELETE CASCADE
);
"""

CREATE_NOTIFICATIONS_TABLE_V4 = """
CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL DEFAULT 'REMINDER',
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'NORMAL',
    source_automation_id TEXT DEFAULT NULL,
    created_at TEXT NOT NULL,
    read_at TEXT DEFAULT NULL,
    status TEXT NOT NULL DEFAULT 'UNREAD'
);
"""

CREATE_INDEX_AUTOMATIONS_STATUS = "CREATE INDEX IF NOT EXISTS idx_automations_status ON automations(status);"
CREATE_INDEX_AUTOMATIONS_NEXT_RUN = "CREATE INDEX IF NOT EXISTS idx_automations_next_run ON automations(next_run_at);"
CREATE_INDEX_RUNS_AUTOMATION_ID = "CREATE INDEX IF NOT EXISTS idx_runs_automation_id ON automation_runs(automation_id);"


def initialize_schema(conn) -> None:
    """Execute schema creation scripts on SQLite connection."""
    with conn:
        conn.execute(CREATE_MEMORIES_TABLE_V1)
        conn.execute(CREATE_INDEX_TYPE)
        conn.execute(CREATE_INDEX_STATUS)
        conn.execute(CREATE_INDEX_PROJECT)

        # Phase 9 Schema
        conn.execute(CREATE_TASKS_TABLE_V3)
        conn.execute(CREATE_TASK_STEPS_TABLE_V3)
        conn.execute(CREATE_TASK_CHECKPOINTS_TABLE_V3)
        conn.execute(CREATE_TASK_EVENTS_TABLE_V3)

        # Phase 10 Schema
        conn.execute(CREATE_AUTOMATIONS_TABLE_V4)
        conn.execute(CREATE_AUTOMATION_RUNS_TABLE_V4)
        conn.execute(CREATE_NOTIFICATIONS_TABLE_V4)
        conn.execute(CREATE_INDEX_AUTOMATIONS_STATUS)
        conn.execute(CREATE_INDEX_AUTOMATIONS_NEXT_RUN)
        conn.execute(CREATE_INDEX_RUNS_AUTOMATION_ID)
