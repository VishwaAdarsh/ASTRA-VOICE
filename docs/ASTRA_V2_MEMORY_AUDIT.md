# ASTRA V2 — Phase 11: Memory Subsystem Audit

## 1. Current Memory Architecture Overview

The current memory subsystem in ASTRA (located in `src/memory/` and `src/tools/memory/`) was developed in Phase 7 as a basic long-term storage mechanism. It provides SQLite-based storage of user facts, preferences, and project information.

### Subsystem Components:
- **`src/memory/models.py`**: Contains `MemoryItem`, `MemoryCandidate`, `MemorySearchQuery`, `MemorySearchResult`, and enums `MemoryType`, `MemorySource`, `MemoryImportance`, `MemoryStatus`, `MemoryPolicyDecision`.
- **`src/memory/repository.py`**: SQLite database persistence layer using `memories` table in `data/astra_memory.db`.
- **`src/memory/policy.py`**: Basic secret regex matching, duplicate prevention, and simple conflict detection.
- **`src/memory/extractor.py`**: Regex-based extraction of explicit "remember that ..." phrases.
- **`src/memory/retriever.py`**: Word overlap and keyword-matching retrieval with heuristic importance boosting.
- **`src/memory/manager.py`**: Façade orchestrating extraction, policy, repository, and retrieval.
- **`src/tools/memory/`**: 4 tools (`RememberTool`, `RetrieveMemoryTool`, `ForgetMemoryTool`, `ListMemoriesTool`) inheriting from `BaseTool`.
- **`src/database/connection.py` & `src/database/schema.py`**: Manages SQLite connection with WAL mode and initializes `memories` table.

---

## 2. Existing Models & Schema

### 2.1 Existing Database Schema (`memories` table)
```sql
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
```

### 2.2 Existing `MemoryItem` Dataclass
```python
@dataclass
class MemoryItem:
    id: int | None
    type: MemoryType
    content: str
    source: MemorySource
    importance: MemoryImportance = MemoryImportance.MEDIUM
    confidence: float = 1.0
    status: MemoryStatus = MemoryStatus.ACTIVE
    project_id: str | None = None
    tags: list[str] = field(default_factory=list)
    created_at: str = ...
    updated_at: str = ...
    last_accessed_at: str = ...
    expires_at: str | None = None
    access_count: int = 0
```

---

## 3. Current Retrieval, Expiration & Retention

### 3.1 Retrieval
- Implemented in `MemoryRetriever.retrieve_relevant()`:
  - Fetches all active memories from the database.
  - Computes word overlap between query terms and memory content.
  - Adds $+0.3$ for `HIGH` importance, $+0.1$ for `MEDIUM` importance, and $+0.4$ if `project_id` matches.
  - Sorts descending by score and caps at `max_retrieved_memories`.
- **Limitations**:
  - Loads all active memories into Python memory.
  - No distinction between explicit and inferred memories.
  - No context budget (character or token limit) applied to prompt context.
  - Does not take into account recency or confidence decay.

### 3.2 Expiration & Retention
- Single global expiration field `expires_at`.
- Cleanup runs `DELETE WHERE expires_at < now`.
- **Limitations**:
  - No type-aware retention policies (e.g. `SESSION`, `SHORT`, `MEDIUM`, `LONG`, `PERSISTENT_UNTIL_CHANGED`).
  - An inferred memory has the exact same retention behavior as a user-confirmed architectural decision.
  - Deletions are hard updates without preserving `SUPERSEDED` or `REVOKED` state audit trails.

---

## 4. Agent & Context Integration

- **Current State**:
  - `AstraAgent` instantiates `self.memory_manager = MemoryManager(config=self.config)`.
  - It registers `RememberTool`, `RetrieveMemoryTool`, `ForgetMemoryTool`, and `ListMemoriesTool`.
  - **Critical Gap**: `ContextManager` does *not* automatically query or inject memory context into the prompt sent to the LLM. The LLM only accesses memory if it proactively chooses to invoke `retrieve_memory` as a tool call!
  - There is no `MemoryContextBuilder` injecting relevant memories with prompt injection protection.

---

## 5. Security & Privacy Audit

- **Current Secret Detection**:
  - Hardcoded regex in `MemoryPolicy.SECRET_PATTERNS` (OpenAI keys, GitHub tokens, bearer tokens, passwords).
  - Does not leverage the centralized `SecretRedactionFilter` from `src.security.redaction` or `PromptInjectionDefense` from `src.security.injection`.
- **Untrusted Data Handling**:
  - Retrieved memory content is not wrapped in structured boundaries (e.g., `<ASTRA_MEMORY>...</ASTRA_MEMORY>`).
  - No explicit instruction isolating stored memories from system commands.

---

## 6. Identified Deficiencies & Problems

1. **Lack of Stable UUIDs**: Uses autoincrement integer `id` which differs across restarts/re-imports.
2. **Missing Memory Categories**: Only has `USER_PREFERENCE`, `USER_FACT`, `PROJECT`, `WORKFLOW`, `TASK`, `SYSTEM`. Missing `WORKING`, `PROFILE`, `EPISODIC`, `PROCEDURAL`.
3. **No Explicit vs. Inferred Distinction**: Cannot distinguish between a direct user instruction ("I like dark mode") and an inference from context.
4. **No Scopes**: Lacks formal `GLOBAL`, `PROJECT`, `SESSION` scopes.
5. **No Structured Lifecycle**: Only `ACTIVE`, `ARCHIVED`, `DELETED`. Missing `SUPERSEDED` and `REVOKED`.
6. **No Automated Context Injection**: The agent prompt lacks an automated, context-aware memory injection step.
7. **No Token/Char Budget**: Injected memory has no configurable character or token ceilings.
8. **No Event Bus Integration**: Memory mutations do not publish structured events to the V2-09 Event Bus.
9. **No Capability Registry Evolution**: Tools are registered as legacy tools without Phase 10 capability risk metadata.

---

## 7. Migration & Evolution Strategy

1. **Non-Destructive Schema Evolution**:
   - Add new columns to `memories` via `ALTER TABLE` migrations: `memory_id` (TEXT UNIQUE), `explicitness`, `retention_policy`, `scope_type`, `scope_id`, `summary`, `source_reference`, `created_from_request_id`, `last_confirmed_at`, `entities`, `privacy_level`, `metadata_json`.
   - Backfill `memory_id` for existing rows (`f"mem_{row['id']}"`).
   - Retain backwards compatibility on `MemoryItem` so existing code referencing `.id` continues to function.
2. **Evolve `MemoryManager` into `MemoryService`**:
   - Maintain `MemoryManager` class or alias to prevent breaking existing imports.
   - Separate concerns into `MemoryRepository`, `MemoryService` (policy, deduplication, conflict resolution), and `MemoryContextBuilder` (retrieval, ranking, prompt formatting).
3. **Integrate with `AstraAgent`**:
   - In `AstraAgent.execute_request`, call `MemoryContextBuilder` to inject safe `<ASTRA_MEMORY>` block into the prompt before LLM invocation.
4. **Publish Safe Events**:
   - Emit `MEMORY_CREATED`, `MEMORY_UPDATED`, `MEMORY_CONFIRMED`, `MEMORY_SUPERSEDED`, `MEMORY_EXPIRED`, `MEMORY_REVOKED` to `EventBus` with redacted metadata.

---

## 8. Files Impacted in V2-11

- **New Files**:
  - `src/memory/service.py` (Central business logic, lifecycle, conflict resolution)
  - `src/memory/context.py` (`MemoryContextBuilder` for prompt injection & budgeting)
  - `docs/ASTRA_V2_MEMORY_AUDIT.md` (This audit document)
  - `docs/ASTRA_V2_MEMORY_ARCHITECTURE.md` (Architecture specification)
  - `tests/test_memory_v2.py` (Comprehensive test suite covering all 30 requirements)
- **Modified Files**:
  - `src/database/schema.py` (Schema migration and V2 table definitions)
  - `src/memory/models.py` (Canonical Memory models, enums, scopes, explicitness, retention)
  - `src/memory/repository.py` (Support for stable string IDs, scopes, retention, lifecycle states)
  - `src/memory/policy.py` (Integration with centralized SecretRedactionFilter, deduplication, conflicts)
  - `src/memory/manager.py` (Updated to leverage MemoryService and maintain backward compatibility)
  - `src/memory/__init__.py` (Subsystem exports)
  - `src/core/events/models.py` (Added `MEMORY_*` event types to `AstraEventType`)
  - `src/core/config.py` (Added memory configuration settings)
  - `src/brain/agent.py` (Context injection via `MemoryContextBuilder`)
  - `src/tools/memory/remember.py`, `forget.py`, `list.py`, `retrieve.py` (Updated to support new fields and operations)
