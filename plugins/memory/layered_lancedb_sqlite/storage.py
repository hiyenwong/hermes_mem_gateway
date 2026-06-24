from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


EMBEDDER_VERSION = "blake2b-counts-v2"
EMBEDDER_STATE_KEY = "embedder_state"

try:
    import lancedb  # type: ignore
    import pyarrow as pa
except Exception:  # pragma: no cover - optional dependency
    lancedb = None
    pa = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def tokenize(text: str) -> list[str]:
    return [
        token
        for token in "".join(ch.lower() if ch.isalnum() else " " for ch in text).split()
        if token
    ]


def _stable_token_slot(token: str, dimensions: int) -> int:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % dimensions


def embed_text(text: str, dimensions: int) -> list[float]:
    vector = [0.0] * dimensions
    for token in tokenize(text):
        vector[_stable_token_slot(token, dimensions)] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"vector length mismatch: {len(a)} vs {len(b)}")
    return sum(x * y for x, y in zip(a, b))


@dataclass
class SearchResult:
    record: dict[str, Any]
    score: float


class SemanticIndex:
    def __init__(self, path: Path, dimensions: int) -> None:
        self.path = path
        self.dimensions = dimensions
        self._lock = threading.Lock()
        self.backend = "lancedb" if lancedb is not None else "stub"
        self._stub_path = self.path / "semantic_index.json"
        self.path.mkdir(parents=True, exist_ok=True)
        self._table = None
        if self.backend == "lancedb":
            self._init_lancedb()

    def _init_lancedb(self) -> None:
        if lancedb is None or pa is None:  # pragma: no cover
            return
        db = lancedb.connect(str(self.path))
        schema = pa.schema(
            [
                pa.field("memory_id", pa.string()),
                pa.field("profile_id", pa.string()),
                pa.field("workspace_id", pa.string()),
                pa.field("principal_id", pa.string()),
                pa.field("platform", pa.string()),
                pa.field("session_id", pa.string()),
                pa.field("layer", pa.string()),
                pa.field("kind", pa.string()),
                pa.field("status", pa.string()),
                pa.field("content", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), self.dimensions)),
            ]
        )
        try:
            self._table = db.open_table("memory_index")
        except Exception:
            self._table = db.create_table("memory_index", schema=schema)

    def _load_stub_rows(self) -> list[dict[str, Any]]:
        if not self._stub_path.exists():
            return []
        raw = self._stub_path.read_text().strip()
        if not raw:
            return []
        return json.loads(raw)

    def _save_stub_rows(self, rows: list[dict[str, Any]]) -> None:
        self._stub_path.write_text(json.dumps(rows, indent=2, sort_keys=True))

    def upsert(self, rows: Iterable[dict[str, Any]]) -> None:
        rows = list(rows)
        if not rows:
            return
        with self._lock:
            self._upsert_locked(rows)

    def remove(self, memory_id: str) -> None:
        with self._lock:
            if (
                self.backend == "lancedb" and self._table is not None
            ):  # pragma: no cover
                self._table.delete(f"memory_id = '{memory_id}'")
                return
            rows = [
                row for row in self._load_stub_rows() if row["memory_id"] != memory_id
            ]
            self._save_stub_rows(rows)

    def search(
        self, query: str, *, filters: dict[str, str], limit: int
    ) -> list[SearchResult]:
        vector = embed_text(query, self.dimensions)
        rows: list[dict[str, Any]]
        if self.backend == "lancedb" and self._table is not None:  # pragma: no cover
            rows = list(self._table.search(vector).limit(max(limit * 3, 10)).to_list())
        else:
            rows = self._load_stub_rows()

        results: list[SearchResult] = []
        for row in rows:
            if any(
                str(row.get(key, "")) != value
                for key, value in filters.items()
                if value
            ):
                continue
            candidate = list(row.get("vector", []))
            if len(candidate) != self.dimensions:
                continue
            score = cosine_similarity(vector, candidate)
            results.append(SearchResult(record=row, score=score))
        results.sort(key=lambda item: item.score, reverse=True)
        return results[:limit]

    def rebuild(self, rows: Iterable[dict[str, Any]]) -> None:
        rows = list(rows)
        with self._lock:
            if self.backend == "lancedb" and lancedb is not None:  # pragma: no cover
                db = lancedb.connect(str(self.path))
                try:
                    db.drop_table("memory_index")
                except Exception:
                    pass
                self._table = None
                self._init_lancedb()
            else:
                self._save_stub_rows([])
            self._upsert_locked(rows)

    def _upsert_locked(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        if self.backend == "lancedb" and self._table is not None:  # pragma: no cover
            payload = [
                {
                    "memory_id": row["memory_id"],
                    "profile_id": row["profile_id"],
                    "workspace_id": row["workspace_id"],
                    "principal_id": row["principal_id"],
                    "platform": row.get("platform", ""),
                    "session_id": row["session_id"],
                    "layer": row["layer"],
                    "kind": row["kind"],
                    "status": row["status"],
                    "content": row["content"],
                    "vector": [float(value) for value in row["vector"]],
                }
                for row in rows
            ]
            self._table.add(payload)
            return
        existing = {row["memory_id"]: row for row in self._load_stub_rows()}
        for row in rows:
            existing[row["memory_id"]] = row
        self._save_stub_rows(list(existing.values()))


class SQLiteStore:
    def __init__(self, db_path: Path, *, dimensions: int, index_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.dimensions = dimensions
        self.index = SemanticIndex(index_path, dimensions)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def bootstrap(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    platform TEXT NOT NULL DEFAULT '',
                    session_id TEXT NOT NULL,
                    layer TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    importance REAL NOT NULL DEFAULT 0.5,
                    reinforcement_count INTEGER NOT NULL DEFAULT 0,
                    access_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_accessed_at TEXT,
                    archived_at TEXT,
                    supersedes_id TEXT,
                    superseded_by_id TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_memories_scope
                    ON memories(profile_id, workspace_id, principal_id, session_id, layer, status);
                CREATE INDEX IF NOT EXISTS idx_memories_fingerprint
                    ON memories(profile_id, workspace_id, principal_id, layer, fingerprint);
                CREATE TABLE IF NOT EXISTS provenance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_ref TEXT,
                    platform TEXT,
                    agent_context TEXT,
                    session_id TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS maintenance_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            # Migrate pre-existing DBs that lack the platform column, then add
            # the platform index (it references the column, so order matters).
            self._ensure_column("memories", "platform", "TEXT NOT NULL DEFAULT ''")
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memories_platform
                    ON memories(profile_id, workspace_id, principal_id, platform, layer, status)
                """
            )
            self._conn.commit()

    def _ensure_column(self, table: str, column: str, ddl: str) -> None:
        cursor = self._conn.execute(f"PRAGMA table_info({table})")
        existing = {str(row["name"]) for row in cursor.fetchall()}
        if column not in existing:
            self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def validate(self) -> dict[str, Any]:
        with self._lock:
            cursor = self._conn.execute("SELECT COUNT(*) AS count FROM memories")
            row = cursor.fetchone()
        return {
            "sqlite_exists": self.db_path.exists(),
            "memory_count": int(row["count"]) if row else 0,
            "index_backend": self.index.backend,
            "index_path": str(self.index.path),
        }

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["metadata"] = json.loads(data.pop("metadata_json", "{}") or "{}")
        return data

    def insert_memory(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        principal_id: str,
        session_id: str,
        layer: str,
        kind: str,
        content: str,
        fingerprint: str,
        source: str,
        importance: float,
        platform: str = "",
        metadata: dict[str, Any] | None = None,
        supersedes_id: str | None = None,
    ) -> str:
        memory_id = str(uuid.uuid4())
        now = utc_now()
        metadata = metadata or {}
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO memories (
                    id, profile_id, workspace_id, principal_id, platform, session_id, layer, kind, content,
                    fingerprint, source, status, importance, created_at, updated_at, metadata_json, supersedes_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    profile_id,
                    workspace_id,
                    principal_id,
                    platform,
                    session_id,
                    layer,
                    kind,
                    content,
                    fingerprint,
                    source,
                    importance,
                    now,
                    now,
                    json.dumps(metadata, sort_keys=True),
                    supersedes_id,
                ),
            )
            if supersedes_id:
                self._conn.execute(
                    "UPDATE memories SET status = 'superseded', superseded_by_id = ?, updated_at = ? WHERE id = ?",
                    (memory_id, now, supersedes_id),
                )
            self._conn.commit()
        if layer.startswith("semantic"):
            self.index.upsert(
                [
                    {
                        "memory_id": memory_id,
                        "profile_id": profile_id,
                        "workspace_id": workspace_id,
                        "principal_id": principal_id,
                        "platform": platform,
                        "session_id": session_id,
                        "layer": layer,
                        "kind": kind,
                        "status": "active",
                        "content": content,
                        "vector": embed_text(content, self.dimensions),
                    }
                ]
            )
        return memory_id

    def add_provenance(
        self,
        memory_id: str,
        *,
        source_type: str,
        source_ref: str = "",
        platform: str = "",
        agent_context: str = "",
        session_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO provenance (
                    memory_id, source_type, source_ref, platform, agent_context, session_id, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    source_type,
                    source_ref,
                    platform,
                    agent_context,
                    session_id,
                    json.dumps(metadata or {}, sort_keys=True),
                    utc_now(),
                ),
            )
            self._conn.commit()

    def reinforce(self, memory_id: str) -> None:
        with self._lock:
            self._conn.execute(
                """
                UPDATE memories
                SET reinforcement_count = reinforcement_count + 1,
                    last_accessed_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (utc_now(), utc_now(), memory_id),
            )
            self._conn.commit()

    def archive(
        self, memory_id: str, metadata_update: dict[str, Any] | None = None
    ) -> None:
        now = utc_now()
        with self._lock:
            if metadata_update:
                cursor = self._conn.execute(
                    "SELECT metadata_json FROM memories WHERE id = ?", (memory_id,)
                )
                row = cursor.fetchone()
                metadata = json.loads(row["metadata_json"] or "{}") if row else {}
                metadata.update(metadata_update)
                self._conn.execute(
                    """
                    UPDATE memories
                    SET status = 'archived', archived_at = ?, updated_at = ?, metadata_json = ?
                    WHERE id = ?
                    """,
                    (now, now, json.dumps(metadata, sort_keys=True), memory_id),
                )
            else:
                self._conn.execute(
                    "UPDATE memories SET status = 'archived', archived_at = ?, updated_at = ? WHERE id = ?",
                    (now, now, memory_id),
                )
            self._conn.commit()
        self.index.remove(memory_id)

    def fetch_existing_durable(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        principal_id: str,
        layer: str,
    ) -> list[dict[str, Any]]:
        with self._lock:
            cursor = self._conn.execute(
                """
                SELECT * FROM memories
                WHERE profile_id = ? AND workspace_id = ? AND principal_id = ? AND layer = ? AND status = 'active'
                ORDER BY created_at DESC
                """,
                (profile_id, workspace_id, principal_id, layer),
            )
            rows = cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]

    def search_exact(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        principal_id: str,
        session_id: str,
        layer: str,
        limit: int,
        date: str = "",
        exclude_session_id: str = "",
        platform: str = "",
    ) -> list[dict[str, Any]]:
        where = [
            "profile_id = ?",
            "workspace_id = ?",
            "layer = ?",
            "status = 'active'",
        ]
        params: list[Any] = [profile_id, workspace_id, layer]
        if principal_id:
            where.append("principal_id = ?")
            params.append(principal_id)
        if platform:
            where.append("platform = ?")
            params.append(platform)
        if session_id:
            where.append("session_id = ?")
            params.append(session_id)
        if exclude_session_id:
            where.append("session_id != ?")
            params.append(exclude_session_id)
        if date:
            where.append("created_at LIKE ?")
            params.append(f"{date}%")
        query = f"""
            SELECT * FROM memories
            WHERE {" AND ".join(where)}
            ORDER BY reinforcement_count DESC, created_at DESC
            LIMIT ?
        """
        params.append(limit)
        with self._lock:
            cursor = self._conn.execute(query, params)
            rows = cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]

    def search_semantic(
        self,
        query: str,
        *,
        profile_id: str,
        workspace_id: str,
        principal_id: str,
        session_id: str,
        layer: str,
        limit: int,
        platform: str = "",
    ) -> list[SearchResult]:
        filters = {
            "profile_id": profile_id,
            "workspace_id": workspace_id,
            "principal_id": principal_id,
            "platform": platform,
            "session_id": session_id if layer == "episodic" else "",
            "layer": layer,
            "status": "active",
        }
        matches = self.index.search(query, filters=filters, limit=limit)
        if not matches and layer == "episodic":
            records = self.search_exact(
                profile_id=profile_id,
                workspace_id=workspace_id,
                principal_id=principal_id,
                session_id=session_id,
                layer=layer,
                limit=limit,
                platform=platform,
            )
            return [
                SearchResult(record=record, score=record["importance"])
                for record in records
            ]

        output: list[SearchResult] = []
        for match in matches:
            with self._lock:
                cursor = self._conn.execute(
                    "SELECT * FROM memories WHERE id = ?", (match.record["memory_id"],)
                )
                row = cursor.fetchone()
            if row is not None:
                output.append(
                    SearchResult(record=self._row_to_dict(row), score=match.score)
                )
        return output

    def eligible_index_rows(self) -> list[dict[str, Any]]:
        with self._lock:
            cursor = self._conn.execute(
                """
                SELECT id, profile_id, workspace_id, principal_id, platform, session_id, layer, kind, status, content
                FROM memories
                WHERE layer LIKE 'semantic%' AND status = 'active'
                """
            )
            rows = cursor.fetchall()
        payload = []
        for row in rows:
            data = dict(row)
            data["memory_id"] = data.pop("id")
            data["vector"] = embed_text(data["content"], self.dimensions)
            payload.append(data)
        return payload

    def list_user_principals(
        self, *, profile_id: str, workspace_id: str
    ) -> list[dict[str, str]]:
        with self._lock:
            cursor = self._conn.execute(
                """
                SELECT principal_id,
                       COALESCE(MAX(json_extract(metadata_json, '$.principal_source')), '') AS principal_source
                FROM memories
                WHERE profile_id = ?
                  AND workspace_id = ?
                  AND layer = 'semantic_user'
                  AND principal_id != ''
                GROUP BY principal_id
                ORDER BY principal_id
                """,
                (profile_id, workspace_id),
            )
            rows = cursor.fetchall()
        return [
            {
                "principal_id": str(row["principal_id"]),
                "principal_source": str(row["principal_source"] or ""),
            }
            for row in rows
        ]

    def fetch_user_records_for_date(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        principal_id: str,
        date: str,
        layer: str = "semantic_user",
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [profile_id, workspace_id, principal_id, layer, f"{date}%"]
        query = """
            SELECT *
            FROM memories
            WHERE profile_id = ?
              AND workspace_id = ?
              AND principal_id = ?
              AND layer = ?
              AND status = 'active'
              AND created_at LIKE ?
            ORDER BY created_at ASC
        """
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        with self._lock:
            cursor = self._conn.execute(query, params)
            rows = cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_maintenance_state(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            cursor = self._conn.execute(
                "SELECT value FROM maintenance_state WHERE key = ?", (key,)
            )
            row = cursor.fetchone()
        if row is None:
            return None
        value = row["value"]
        try:
            data = json.loads(value)
        except json.JSONDecodeError:
            return {"status": "unknown", "value": value}
        return data if isinstance(data, dict) else {"status": "unknown", "value": data}

    def set_maintenance_state(self, key: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO maintenance_state(key, value, updated_at) VALUES (?, ?, ?)",
                (key, json.dumps(value, sort_keys=True), utc_now()),
            )
            self._conn.commit()

    def backfill_platform_from_provenance(
        self, *, dry_run: bool = True
    ) -> dict[str, int]:
        """Backfill memories.platform for legacy rows using provenance records.

        Rows written before the platform column existed default to ''. The
        provenance table preserves the platform value seen at write time, so we
        copy the earliest non-empty provenance.platform into the memory row.
        Rows whose provenance also lacks a platform cannot be recovered and are
        reported as ``remaining_empty``.
        """
        with self._lock:
            empty_before = int(
                self._conn.execute(
                    "SELECT COUNT(*) AS c FROM memories WHERE platform = ''"
                ).fetchone()["c"]
            )
            fillable = int(
                self._conn.execute(
                    """
                    SELECT COUNT(*) AS c FROM memories m
                    WHERE m.platform = ''
                      AND EXISTS (
                        SELECT 1 FROM provenance p
                        WHERE p.memory_id = m.id
                          AND p.platform IS NOT NULL
                          AND p.platform != ''
                      )
                    """
                ).fetchone()["c"]
            )
            updated = 0
            if not dry_run and fillable:
                cursor = self._conn.execute(
                    """
                    UPDATE memories
                    SET platform = (
                        SELECT p.platform FROM provenance p
                        WHERE p.memory_id = memories.id
                          AND p.platform IS NOT NULL
                          AND p.platform != ''
                        ORDER BY p.created_at ASC, p.id ASC
                        LIMIT 1
                    ),
                    updated_at = ?
                    WHERE platform = ''
                      AND EXISTS (
                        SELECT 1 FROM provenance p
                        WHERE p.memory_id = memories.id
                          AND p.platform IS NOT NULL
                          AND p.platform != ''
                      )
                    """,
                    (utc_now(),),
                )
                updated = cursor.rowcount
                self._conn.commit()
            remaining_empty = empty_before - updated
        return {
            "empty_before": empty_before,
            "fillable": fillable,
            "updated": updated,
            "remaining_empty": remaining_empty,
        }

    def rebuild_index(self) -> int:
        rows = self.eligible_index_rows()
        self.index.rebuild(rows)
        self._persist_embedder_state(len(rows))
        return len(rows)

    def ensure_index_current(self) -> dict[str, Any]:
        current = {"version": EMBEDDER_VERSION, "dimensions": self.dimensions}
        state = self.get_maintenance_state(EMBEDDER_STATE_KEY) or {}
        if (
            state.get("version") == current["version"]
            and int(state.get("dimensions", -1)) == self.dimensions
        ):
            return {"rebuilt": False, **current}
        rebuilt_count = self.rebuild_index()
        return {"rebuilt": True, "rebuilt_count": rebuilt_count, **current}

    def _persist_embedder_state(self, rebuilt_count: int) -> None:
        now = utc_now()
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO maintenance_state(key, value, updated_at) VALUES (?, ?, ?)",
                ("last_rebuild_count", str(rebuilt_count), now),
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO maintenance_state(key, value, updated_at) VALUES (?, ?, ?)",
                (
                    EMBEDDER_STATE_KEY,
                    json.dumps(
                        {"version": EMBEDDER_VERSION, "dimensions": self.dimensions},
                        sort_keys=True,
                    ),
                    now,
                ),
            )
            self._conn.commit()
