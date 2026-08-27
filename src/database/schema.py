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


def initialize_schema(conn) -> None:
    """Execute schema creation scripts on SQLite connection."""
    with conn:
        conn.execute(CREATE_MEMORIES_TABLE_V1)
        conn.execute(CREATE_INDEX_TYPE)
        conn.execute(CREATE_INDEX_STATUS)
        conn.execute(CREATE_INDEX_PROJECT)
