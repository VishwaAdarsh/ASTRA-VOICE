"""
Memory Repository Subsystem.
Provides low-level SQLite persistence, queries, updates, and soft deletions for MemoryItem.
"""

from datetime import datetime
from typing import Any
from src.core.config import Config
from src.core.exceptions import MemoryDatabaseError, MemoryNotFoundError
from src.core.logger import get_logger
from src.database.connection import DatabaseManager
from src.memory.models import (
    MemoryImportance,
    MemoryItem,
    MemorySource,
    MemoryStatus,
    MemoryType,
)

logger = get_logger()


class MemoryRepository:
    """SQLite repository for MemoryItem persistence."""

    def __init__(self, db_manager: DatabaseManager | None = None, config: Config | None = None):
        self.config = config or Config()
        self.db_manager = db_manager or DatabaseManager(config=self.config)

    def add(self, item: MemoryItem) -> MemoryItem:
        """Insert a new memory record into the database."""
        now_str = datetime.now().isoformat()
        tags_str = ",".join(item.tags) if item.tags else ""

        sql = """
        INSERT INTO memories (
            type, content, source, importance, confidence, status, project_id, tags,
            created_at, updated_at, last_accessed_at, expires_at, access_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params = (
            item.type.value if isinstance(item.type, MemoryType) else str(item.type),
            item.content,
            item.source.value if isinstance(item.source, MemorySource) else str(item.source),
            item.importance.value if isinstance(item.importance, MemoryImportance) else str(item.importance),
            item.confidence,
            item.status.value if isinstance(item.status, MemoryStatus) else str(item.status),
            item.project_id,
            tags_str,
            now_str,
            now_str,
            now_str,
            item.expires_at,
            item.access_count,
        )

        try:
            conn = self.db_manager.get_connection()
            with conn:
                cursor = conn.execute(sql, params)
                new_id = cursor.lastrowid
            conn.close()

            item.id = new_id
            item.created_at = now_str
            item.updated_at = now_str
            item.last_accessed_at = now_str
            logger.info(f"MemoryRepository: Inserted memory #{new_id} ({item.type.value}): '{item.content}'")
            return item
        except Exception as e:
            logger.error(f"MemoryRepository.add failed: {e}")
            raise MemoryDatabaseError(f"Failed to insert memory item: {e}")

    def get_by_id(self, memory_id: int) -> MemoryItem | None:
        """Retrieve active or archived memory record by ID."""
        sql = "SELECT * FROM memories WHERE id = ? AND status != 'DELETED';"
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.execute(sql, (memory_id,))
            row = cursor.fetchone()
            conn.close()

            if row:
                return self._row_to_item(row)
            return None
        except Exception as e:
            logger.error(f"MemoryRepository.get_by_id failed for id {memory_id}: {e}")
            raise MemoryDatabaseError(f"Failed to retrieve memory item #{memory_id}: {e}")

    def update(self, item: MemoryItem) -> MemoryItem:
        """Update existing memory record content, importance, or timestamps."""
        if not item.id:
            raise MemoryDatabaseError("Cannot update memory item without valid ID.")

        now_str = datetime.now().isoformat()
        tags_str = ",".join(item.tags) if item.tags else ""

        sql = """
        UPDATE memories SET
            type = ?, content = ?, source = ?, importance = ?, confidence = ?,
            status = ?, project_id = ?, tags = ?, updated_at = ?, expires_at = ?
        WHERE id = ?;
        """
        params = (
            item.type.value if isinstance(item.type, MemoryType) else str(item.type),
            item.content,
            item.source.value if isinstance(item.source, MemorySource) else str(item.source),
            item.importance.value if isinstance(item.importance, MemoryImportance) else str(item.importance),
            item.confidence,
            item.status.value if isinstance(item.status, MemoryStatus) else str(item.status),
            item.project_id,
            tags_str,
            now_str,
            item.expires_at,
            item.id,
        )

        try:
            conn = self.db_manager.get_connection()
            with conn:
                conn.execute(sql, params)
            conn.close()

            item.updated_at = now_str
            logger.info(f"MemoryRepository: Updated memory #{item.id}")
            return item
        except Exception as e:
            logger.error(f"MemoryRepository.update failed: {e}")
            raise MemoryDatabaseError(f"Failed to update memory item #{item.id}: {e}")

    def delete(self, memory_id: int) -> bool:
        """Soft-delete a memory item by marking status as DELETED."""
        sql = "UPDATE memories SET status = 'DELETED', updated_at = ? WHERE id = ?;"
        now_str = datetime.now().isoformat()
        try:
            conn = self.db_manager.get_connection()
            with conn:
                cursor = conn.execute(sql, (now_str, memory_id))
                affected = cursor.rowcount
            conn.close()
            logger.info(f"MemoryRepository: Soft-deleted memory #{memory_id}")
            return affected > 0
        except Exception as e:
            logger.error(f"MemoryRepository.delete failed for id {memory_id}: {e}")
            raise MemoryDatabaseError(f"Failed to delete memory item #{memory_id}: {e}")

    def clear_all(self, exclude_system: bool = True) -> int:
        """Clear active/archived memories (marks as DELETED). Excludes SYSTEM memory by default."""
        now_str = datetime.now().isoformat()
        if exclude_system:
            sql = "UPDATE memories SET status = 'DELETED', updated_at = ? WHERE type != 'SYSTEM' AND status != 'DELETED';"
            params = (now_str,)
        else:
            sql = "UPDATE memories SET status = 'DELETED', updated_at = ? WHERE status != 'DELETED';"
            params = (now_str,)

        try:
            conn = self.db_manager.get_connection()
            with conn:
                cursor = conn.execute(sql, params)
                count = cursor.rowcount
            conn.close()
            logger.info(f"MemoryRepository: Cleared {count} memory records.")
            return count
        except Exception as e:
            logger.error(f"MemoryRepository.clear_all failed: {e}")
            raise MemoryDatabaseError(f"Failed to clear memories: {e}")

    def search(self, query: str, memory_type: MemoryType | None = None, limit: int = 10) -> list[MemoryItem]:
        """Search active memory records matching content query or type."""
        sql = "SELECT * FROM memories WHERE status = 'ACTIVE'"
        params: list[Any] = []

        if query and query.strip():
            sql += " AND content LIKE ?"
            params.append(f"%{query.strip()}%")

        if memory_type:
            sql += " AND type = ?"
            params.append(memory_type.value if isinstance(memory_type, MemoryType) else str(memory_type))

        sql += " ORDER BY updated_at DESC LIMIT ?;"
        params.append(limit)

        try:
            conn = self.db_manager.get_connection()
            cursor = conn.execute(sql, tuple(params))
            rows = cursor.fetchall()
            conn.close()

            return [self._row_to_item(row) for row in rows]
        except Exception as e:
            logger.error(f"MemoryRepository.search failed: {e}")
            raise MemoryDatabaseError(f"Search failed for query '{query}': {e}")

    def list_all(self, status: MemoryStatus = MemoryStatus.ACTIVE) -> list[MemoryItem]:
        """Retrieve all memory records matching specified status."""
        sql = "SELECT * FROM memories WHERE status = ? ORDER BY updated_at DESC;"
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.execute(sql, (status.value if isinstance(status, MemoryStatus) else str(status),))
            rows = cursor.fetchall()
            conn.close()

            return [self._row_to_item(row) for row in rows]
        except Exception as e:
            logger.error(f"MemoryRepository.list_all failed: {e}")
            raise MemoryDatabaseError(f"Failed to list memories: {e}")

    def touch(self, memory_id: int) -> None:
        """Update last_accessed_at timestamp and increment access count."""
        now_str = datetime.now().isoformat()
        sql = "UPDATE memories SET last_accessed_at = ?, access_count = access_count + 1 WHERE id = ?;"
        try:
            conn = self.db_manager.get_connection()
            with conn:
                conn.execute(sql, (now_str, memory_id))
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to touch memory #{memory_id}: {e}")

    def cleanup_expired(self) -> int:
        """Mark expired temporary memories as DELETED."""
        now_str = datetime.now().isoformat()
        sql = "UPDATE memories SET status = 'DELETED' WHERE expires_at IS NOT NULL AND expires_at < ? AND status != 'DELETED';"
        try:
            conn = self.db_manager.get_connection()
            with conn:
                cursor = conn.execute(sql, (now_str,))
                count = cursor.rowcount
            conn.close()
            if count > 0:
                logger.info(f"MemoryRepository: Cleaned up {count} expired memory records.")
            return count
        except Exception as e:
            logger.error(f"MemoryRepository.cleanup_expired failed: {e}")
            return 0

    def _row_to_item(self, row: sqlite3.Row) -> MemoryItem:
        """Convert a sqlite3.Row dict into a MemoryItem instance."""
        tags_raw = row["tags"] or ""
        tags_list = [t.strip() for t in tags_raw.split(",") if t.strip()]

        return MemoryItem(
            id=row["id"],
            type=MemoryType(row["type"]),
            content=row["content"],
            source=MemorySource(row["source"]),
            importance=MemoryImportance(row["importance"]),
            confidence=float(row["confidence"]),
            status=MemoryStatus(row["status"]),
            project_id=row["project_id"],
            tags=tags_list,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_accessed_at=row["last_accessed_at"],
            expires_at=row["expires_at"],
            access_count=int(row["access_count"]),
        )
