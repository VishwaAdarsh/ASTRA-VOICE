"""
Database Connection Manager.
Thread-safe connection provider for SQLite memory database.
"""

import sqlite3
from pathlib import Path
from src.core.config import Config
from src.core.logger import get_logger
from src.database.schema import initialize_schema

logger = get_logger()


class DatabaseManager:
    """Manages SQLite connection lifecycle and schema migrations."""

    def __init__(self, config: Config | None = None, db_path: Path | str | None = None):
        self.config = config or Config()
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = self.config.database_path

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def get_connection(self) -> sqlite3.Connection:
        """Create and configure a new SQLite connection with dict row factory."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_database(self) -> None:
        """Initialize database tables and indexes."""
        try:
            conn = self.get_connection()
            initialize_schema(conn)
            conn.close()
            logger.info(f"DatabaseManager initialized at '{self.db_path}'")
        except Exception as e:
            logger.error(f"Failed to initialize database at '{self.db_path}': {e}")
            raise
