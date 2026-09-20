"""
Memory Repository Subsystem (Memory V2).
Provides SQLite persistence, queries, updates, soft-deletion, superseding, and retention cleanup for MemoryItem.
"""

from datetime import datetime, timedelta
import json
import sqlite3
from typing import Any, Optional
import uuid

from src.core.config import Config
from src.core.exceptions import MemoryDatabaseError, MemoryNotFoundError
from src.core.logger import get_logger
from src.database.connection import DatabaseManager
from src.memory.models import (
    MemoryExplicitness,
    MemoryImportance,
    MemoryItem,
    MemoryScope,
    MemorySource,
    MemoryStatus,
    MemoryType,
    RetentionPolicy,
)

logger = get_logger()


class MemoryRepository:
    """SQLite repository for canonical MemoryItem persistence."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None, config: Optional[Config] = None):
        self.config = config or Config()
        self.db_manager = db_manager or DatabaseManager(config=self.config)

    def add(self, item: MemoryItem) -> MemoryItem:
        """Insert a new memory record into the database."""
        now_str = datetime.now().isoformat()
        if not item.memory_id:
            item.memory_id = f"mem_{uuid.uuid4().hex[:12]}"

        tags_str = ",".join(item.tags) if item.tags else ""
        entities_str = ",".join(item.entities) if item.entities else ""
        meta_str = json.dumps(item.metadata) if item.metadata else "{}"

        # Calculate expires_at based on retention policy if not set
        if not item.expires_at:
            item.expires_at = self._compute_expiration(item.retention_policy, item.explicitness)

        sql = """
        INSERT INTO memories (
            memory_id, type, content, summary, source, source_reference, created_from_request_id,
            importance, confidence, explicitness, retention_policy, status, scope_type, scope_id,
            project_id, tags, entities, privacy_level, metadata_json,
            created_at, updated_at, last_accessed_at, last_confirmed_at, expires_at, access_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params = (
            item.memory_id,
            item.type.value if hasattr(item.type, "value") else str(item.type),
            item.content,
            item.summary,
            item.source.value if hasattr(item.source, "value") else str(item.source),
            item.source_reference,
            item.created_from_request_id,
            item.importance.value if hasattr(item.importance, "value") else str(item.importance),
            item.confidence,
            item.explicitness.value if hasattr(item.explicitness, "value") else str(item.explicitness),
            item.retention_policy.value if hasattr(item.retention_policy, "value") else str(item.retention_policy),
            item.status.value if hasattr(item.status, "value") else str(item.status),
            item.scope_type.value if hasattr(item.scope_type, "value") else str(item.scope_type),
            item.scope_id,
            item.project_id,
            tags_str,
            entities_str,
            item.privacy_level,
            meta_str,
            now_str,
            now_str,
            now_str,
            item.last_confirmed_at,
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
            logger.info(f"MemoryRepository: Inserted memory #{item.id} ({item.memory_id}): '{item.content}'")
            return item
        except Exception as e:
            logger.error(f"MemoryRepository.add failed: {e}")
            raise MemoryDatabaseError(f"Failed to insert memory item: {e}")

    def get_by_id(self, memory_id: str | int, include_revoked: bool = False) -> Optional[MemoryItem]:
        """Retrieve active, superseded, or archived memory record by string memory_id or integer id."""
        try:
            conn = self.db_manager.get_connection()
            is_num = isinstance(memory_id, int) or (isinstance(memory_id, str) and memory_id.isdigit())
            id_col = "id" if is_num else "memory_id"
            param_val = int(memory_id) if is_num else str(memory_id)

            if include_revoked:
                sql = f"SELECT * FROM memories WHERE {id_col} = ?;"
            else:
                sql = f"SELECT * FROM memories WHERE {id_col} = ? AND status NOT IN ('DELETED', 'REVOKED');"

            cursor = conn.execute(sql, (param_val,))
            row = cursor.fetchone()
            conn.close()

            if row:
                return self._row_to_item(row)
            return None
        except Exception as e:
            logger.error(f"MemoryRepository.get_by_id failed for id {memory_id}: {e}")
            raise MemoryDatabaseError(f"Failed to retrieve memory item #{memory_id}: {e}")

    def update(self, item: MemoryItem) -> MemoryItem:
        """Update existing memory record content, importance, status, or timestamps."""
        if not item.id and not item.memory_id:
            raise MemoryDatabaseError("Cannot update memory item without valid id or memory_id.")

        now_str = datetime.now().isoformat()
        tags_str = ",".join(item.tags) if item.tags else ""
        entities_str = ",".join(item.entities) if item.entities else ""
        meta_str = json.dumps(item.metadata) if item.metadata else "{}"

        sql = """
        UPDATE memories SET
            type = ?, content = ?, summary = ?, source = ?, source_reference = ?,
            importance = ?, confidence = ?, explicitness = ?, retention_policy = ?,
            status = ?, scope_type = ?, scope_id = ?, project_id = ?, tags = ?,
            entities = ?, privacy_level = ?, metadata_json = ?, updated_at = ?,
            last_confirmed_at = ?, expires_at = ?, superseded_by = ?, revocation_reason = ?
        WHERE (id = ? OR memory_id = ?);
        """
        params = (
            item.type.value if hasattr(item.type, "value") else str(item.type),
            item.content,
            item.summary,
            item.source.value if hasattr(item.source, "value") else str(item.source),
            item.source_reference,
            item.importance.value if hasattr(item.importance, "value") else str(item.importance),
            item.confidence,
            item.explicitness.value if hasattr(item.explicitness, "value") else str(item.explicitness),
            item.retention_policy.value if hasattr(item.retention_policy, "value") else str(item.retention_policy),
            item.status.value if hasattr(item.status, "value") else str(item.status),
            item.scope_type.value if hasattr(item.scope_type, "value") else str(item.scope_type),
            item.scope_id,
            item.project_id,
            tags_str,
            entities_str,
            item.privacy_level,
            meta_str,
            now_str,
            item.last_confirmed_at,
            item.expires_at,
            item.superseded_by,
            item.revocation_reason,
            item.id,
            item.memory_id,
        )

        try:
            conn = self.db_manager.get_connection()
            with conn:
                conn.execute(sql, params)
            conn.close()

            item.updated_at = now_str
            logger.info(f"MemoryRepository: Updated memory #{item.id or item.memory_id}")
            return item
        except Exception as e:
            logger.error(f"MemoryRepository.update failed: {e}")
            raise MemoryDatabaseError(f"Failed to update memory item #{item.id or item.memory_id}: {e}")

    def delete(self, memory_id: str | int, soft: bool = True, reason: str = "") -> bool:
        """Delete or revoke a memory item by ID."""
        now_str = datetime.now().isoformat()
        try:
            conn = self.db_manager.get_connection()
            with conn:
                is_num = isinstance(memory_id, int) or (isinstance(memory_id, str) and memory_id.isdigit())
                id_col = "id" if is_num else "memory_id"
                param_val = int(memory_id) if is_num else str(memory_id)

                if soft:
                    sql = f"UPDATE memories SET status = 'REVOKED', revocation_reason = ?, updated_at = ? WHERE {id_col} = ?;"
                    cursor = conn.execute(sql, (reason, now_str, param_val))
                else:
                    sql = f"DELETE FROM memories WHERE {id_col} = ?;"
                    cursor = conn.execute(sql, (param_val,))

                affected = cursor.rowcount
            conn.close()
            logger.info(f"MemoryRepository: Deleted/Revoked memory #{memory_id} (affected={affected})")
            return affected > 0
        except Exception as e:
            logger.error(f"MemoryRepository.delete failed for id {memory_id}: {e}")
            raise MemoryDatabaseError(f"Failed to delete memory item #{memory_id}: {e}")

    def supersede(self, old_id: str | int, new_id: str | int) -> bool:
        """Mark an older memory item as SUPERSEDED by a newer one."""
        now_str = datetime.now().isoformat()
        try:
            conn = self.db_manager.get_connection()
            with conn:
                is_num = isinstance(old_id, int) or (isinstance(old_id, str) and old_id.isdigit())
                id_col = "id" if is_num else "memory_id"
                param_val = int(old_id) if is_num else str(old_id)

                sql = f"UPDATE memories SET status = 'SUPERSEDED', superseded_by = ?, updated_at = ? WHERE {id_col} = ?;"
                cursor = conn.execute(sql, (str(new_id), now_str, param_val))
                affected = cursor.rowcount
            conn.close()
            logger.info(f"MemoryRepository: Marked memory #{old_id} as SUPERSEDED by #{new_id}")
            return affected > 0
        except Exception as e:
            logger.error(f"MemoryRepository.supersede failed for {old_id}: {e}")
            raise MemoryDatabaseError(f"Failed to supersede memory item #{old_id}: {e}")

    def revoke(self, memory_id: str | int, reason: str = "") -> bool:
        """Mark a memory item as REVOKED."""
        return self.delete(memory_id, soft=True, reason=reason)

    def confirm(self, memory_id: str | int) -> bool:
        """Confirm a memory item (updates last_confirmed_at, explicitness, confidence, and retention)."""
        now_str = datetime.now().isoformat()
        try:
            conn = self.db_manager.get_connection()
            with conn:
                is_num = isinstance(memory_id, int) or (isinstance(memory_id, str) and memory_id.isdigit())
                id_col = "id" if is_num else "memory_id"
                param_val = int(memory_id) if is_num else str(memory_id)

                sql = f"""
                UPDATE memories SET
                    last_confirmed_at = ?,
                    explicitness = 'EXPLICIT',
                    confidence = 1.0,
                    retention_policy = 'PERMANENT',
                    updated_at = ?
                WHERE {id_col} = ?;
                """
                cursor = conn.execute(sql, (now_str, now_str, param_val))
                affected = cursor.rowcount
            conn.close()
            logger.info(f"MemoryRepository: Confirmed memory #{memory_id}")
            return affected > 0
        except Exception as e:
            logger.error(f"MemoryRepository.confirm failed for {memory_id}: {e}")
            raise MemoryDatabaseError(f"Failed to confirm memory item #{memory_id}: {e}")

    def clear_all(self, exclude_system: bool = True) -> int:
        """Clear memories (marks as REVOKED / DELETED)."""
        now_str = datetime.now().isoformat()
        if exclude_system:
            sql = "UPDATE memories SET status = 'REVOKED', updated_at = ? WHERE type != 'SYSTEM' AND status NOT IN ('DELETED', 'REVOKED');"
            params = (now_str,)
        else:
            sql = "UPDATE memories SET status = 'REVOKED', updated_at = ? WHERE status NOT IN ('DELETED', 'REVOKED');"
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

    def search(
        self,
        query: str = "",
        memory_type: Optional[MemoryType] = None,
        scope_type: Optional[MemoryScope] = None,
        project_id: Optional[str] = None,
        status: MemoryStatus = MemoryStatus.ACTIVE,
        limit: int = 10,
    ) -> list[MemoryItem]:
        """Search memory records with filtering and keyword matching."""
        status_val = status.value if hasattr(status, "value") else str(status)
        sql = "SELECT * FROM memories WHERE status = ?"
        params: list[Any] = [status_val]

        if query and query.strip():
            sql += " AND (content LIKE ? OR summary LIKE ? OR tags LIKE ? OR entities LIKE ?)"
            term = f"%{query.strip()}%"
            params.extend([term, term, term, term])

        if memory_type:
            sql += " AND type = ?"
            params.append(memory_type.value if hasattr(memory_type, "value") else str(memory_type))

        if scope_type:
            sql += " AND scope_type = ?"
            params.append(scope_type.value if hasattr(scope_type, "value") else str(scope_type))

        if project_id:
            sql += " AND (project_id = ? OR scope_id = ? OR scope_type = 'GLOBAL')"
            params.extend([project_id, project_id])

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

    def list_all(
        self,
        status: MemoryStatus = MemoryStatus.ACTIVE,
        scope_type: Optional[MemoryScope] = None,
        project_id: Optional[str] = None,
    ) -> list[MemoryItem]:
        """Retrieve all memory records matching specified status and scope."""
        status_val = status.value if hasattr(status, "value") else str(status)
        sql = "SELECT * FROM memories WHERE status = ?"
        params: list[Any] = [status_val]

        if scope_type:
            sql += " AND scope_type = ?"
            params.append(scope_type.value if hasattr(scope_type, "value") else str(scope_type))

        if project_id:
            sql += " AND (project_id = ? OR scope_id = ? OR scope_type = 'GLOBAL')"
            params.extend([project_id, project_id])

        sql += " ORDER BY updated_at DESC;"

        try:
            conn = self.db_manager.get_connection()
            cursor = conn.execute(sql, tuple(params))
            rows = cursor.fetchall()
            conn.close()

            return [self._row_to_item(row) for row in rows]
        except Exception as e:
            logger.error(f"MemoryRepository.list_all failed: {e}")
            raise MemoryDatabaseError(f"Failed to list memories: {e}")

    def touch(self, memory_id: str | int) -> None:
        """Update last_accessed_at timestamp and increment access count."""
        now_str = datetime.now().isoformat()
        is_num = isinstance(memory_id, int) or (isinstance(memory_id, str) and memory_id.isdigit())
        id_col = "id" if is_num else "memory_id"
        param_val = int(memory_id) if is_num else str(memory_id)

        sql = f"UPDATE memories SET last_accessed_at = ?, access_count = access_count + 1 WHERE {id_col} = ?;"
        try:
            conn = self.db_manager.get_connection()
            with conn:
                conn.execute(sql, (now_str, param_val))
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to touch memory #{memory_id}: {e}")

    def cleanup_expired(self) -> int:
        """Mark expired memories as EXPIRED based on explicit expires_at or retention policy."""
        now = datetime.now()
        now_str = now.isoformat()
        count = 0

        try:
            conn = self.db_manager.get_connection()
            with conn:
                # 1. Direct expiration via expires_at
                sql1 = "UPDATE memories SET status = 'EXPIRED', updated_at = ? WHERE expires_at IS NOT NULL AND expires_at < ? AND status = 'ACTIVE';"
                cursor1 = conn.execute(sql1, (now_str, now_str))
                count += cursor1.rowcount

                # 2. Inferred memory policy-based expiration
                # SHORT inferred: 1 day
                short_limit = (now - timedelta(days=1)).isoformat()
                sql2 = """
                UPDATE memories SET status = 'EXPIRED', updated_at = ?
                WHERE retention_policy = 'SHORT' AND explicitness = 'INFERRED'
                  AND last_confirmed_at IS NULL AND created_at < ? AND status = 'ACTIVE';
                """
                cursor2 = conn.execute(sql2, (now_str, short_limit))
                count += cursor2.rowcount

                # MEDIUM inferred: default 7 days
                inferred_days = getattr(self.config, "memory_inferred_retention_days", 7)
                medium_limit = (now - timedelta(days=inferred_days)).isoformat()
                sql3 = """
                UPDATE memories SET status = 'EXPIRED', updated_at = ?
                WHERE retention_policy IN ('MEDIUM', 'TIME_BOUND', 'AUTO_CLEANUP') AND explicitness = 'INFERRED'
                  AND last_confirmed_at IS NULL AND created_at < ? AND status = 'ACTIVE';
                """
                cursor3 = conn.execute(sql3, (now_str, medium_limit))
                count += cursor3.rowcount

            conn.close()
            if count > 0:
                logger.info(f"MemoryRepository: Cleaned up {count} expired memory records.")
            return count
        except Exception as e:
            logger.error(f"MemoryRepository.cleanup_expired failed: {e}")
            return 0

    def _compute_expiration(self, policy: RetentionPolicy, explicitness: MemoryExplicitness) -> Optional[str]:
        """Compute ISO expiration date string based on policy and explicitness."""
        now = datetime.now()
        pol_str = policy.value if hasattr(policy, "value") else str(policy)
        if pol_str in ("PERMANENT", "PERSISTENT_UNTIL_CHANGED"):
            return None
        elif pol_str in ("SESSION", "SESSION_BOUND"):
            return (now + timedelta(hours=12)).isoformat()
        elif pol_str in ("SHORT",):
            return (now + timedelta(days=1)).isoformat()
        elif pol_str in ("TIME_BOUND", "MEDIUM", "AUTO_CLEANUP"):
            days = getattr(self.config, "memory_inferred_retention_days", 7) if explicitness == MemoryExplicitness.INFERRED else 30
            return (now + timedelta(days=days)).isoformat()
        elif pol_str in ("LONG",):
            days = getattr(self.config, "memory_expiration_days", 30)
            return (now + timedelta(days=days)).isoformat()
        return None

    def _row_to_item(self, row: sqlite3.Row) -> MemoryItem:
        """Convert a sqlite3.Row dict into a canonical MemoryItem instance."""
        tags_raw = row["tags"] or ""
        tags_list = [t.strip() for t in tags_raw.split(",") if t.strip()]

        entities_raw = row["entities"] if "entities" in row.keys() and row["entities"] else ""
        entities_list = [e.strip() for e in entities_raw.split(",") if e.strip()]

        meta_raw = row["metadata_json"] if "metadata_json" in row.keys() and row["metadata_json"] else "{}"
        try:
            metadata = json.loads(meta_raw)
        except Exception:
            metadata = {}

        # Safely extract V2 fields with defaults if legacy row
        memory_id = row["memory_id"] if "memory_id" in row.keys() and row["memory_id"] else f"mem_legacy_{row['id']}"
        summary = row["summary"] if "summary" in row.keys() and row["summary"] else ""
        source_ref = row["source_reference"] if "source_reference" in row.keys() and row["source_reference"] else ""
        req_id = row["created_from_request_id"] if "created_from_request_id" in row.keys() and row["created_from_request_id"] else ""
        explicitness = row["explicitness"] if "explicitness" in row.keys() and row["explicitness"] else "EXPLICIT"
        retention = row["retention_policy"] if "retention_policy" in row.keys() and row["retention_policy"] else "LONG"
        scope_type = row["scope_type"] if "scope_type" in row.keys() and row["scope_type"] else "GLOBAL"
        scope_id = row["scope_id"] if "scope_id" in row.keys() and row["scope_id"] else ""
        privacy = row["privacy_level"] if "privacy_level" in row.keys() and row["privacy_level"] else "NORMAL"
        last_confirmed = row["last_confirmed_at"] if "last_confirmed_at" in row.keys() else None
        superseded_by = row["superseded_by"] if "superseded_by" in row.keys() else None
        revocation_reason = row["revocation_reason"] if "revocation_reason" in row.keys() else None

        return MemoryItem(
            id=row["id"],
            memory_id=memory_id,
            type=MemoryType(row["type"]) if row["type"] in MemoryType.__members__ else MemoryType.PROFILE,
            content=row["content"],
            summary=summary,
            source=MemorySource(row["source"]) if row["source"] in MemorySource.__members__ else str(row["source"]),
            source_reference=source_ref,
            source_ref=source_ref,
            created_from_request_id=req_id,
            importance=MemoryImportance(row["importance"]) if row["importance"] in MemoryImportance.__members__ else MemoryImportance.MEDIUM,
            confidence=float(row["confidence"]),
            explicitness=MemoryExplicitness(explicitness) if explicitness in MemoryExplicitness.__members__ else MemoryExplicitness.EXPLICIT,
            retention_policy=RetentionPolicy(retention) if retention in RetentionPolicy.__members__ else RetentionPolicy.PERMANENT,
            status=MemoryStatus(row["status"]) if row["status"] in MemoryStatus.__members__ else MemoryStatus.ACTIVE,
            scope_type=MemoryScope(scope_type) if scope_type in MemoryScope.__members__ else MemoryScope.GLOBAL,
            scope_id=scope_id,
            project_id=row["project_id"],
            tags=tags_list,
            entities=entities_list,
            privacy_level=privacy,
            metadata=metadata,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_accessed_at=row["last_accessed_at"],
            last_confirmed_at=last_confirmed,
            expires_at=row["expires_at"],
            access_count=int(row["access_count"]),
            superseded_by=superseded_by,
            revocation_reason=revocation_reason,
        )
