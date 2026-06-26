from __future__ import annotations

import sqlite3
from pathlib import Path

from plugins.memory.layered_lancedb_sqlite.governance import fingerprint_text
from plugins.memory.layered_lancedb_sqlite.storage import SQLiteStore


def _store(tmp_path: Path) -> SQLiteStore:
    store = SQLiteStore(
        tmp_path / "memory.sqlite3",
        dimensions=16,
        index_path=tmp_path / "lancedb",
    )
    store.bootstrap()
    return store


def test_insert_persists_identity_and_recall_carries_it(tmp_path: Path) -> None:
    store = _store(tmp_path)
    try:
        store.insert_memory(
            profile_id="p",
            workspace_id="w",
            principal_id="user-123",
            session_id="s",
            layer="semantic_user",
            kind="explicit_memory",
            content="remember sencha",
            fingerprint=fingerprint_text("remember sencha"),
            source="test",
            importance=0.9,
            platform="cli",
            user_id="user-123",
            user_email="doris@example.com",
            user_name="Doris",
        )
        rows = store.search_exact(
            profile_id="p",
            workspace_id="w",
            principal_id="user-123",
            session_id="",
            layer="semantic_user",
            limit=10,
        )
        assert len(rows) == 1
        record = rows[0]
        assert record["user_id"] == "user-123"
        assert record["user_email"] == "doris@example.com"
        assert record["user_name"] == "Doris"
    finally:
        store.close()


def test_identity_columns_default_to_empty(tmp_path: Path) -> None:
    store = _store(tmp_path)
    try:
        store.insert_memory(
            profile_id="p",
            workspace_id="w",
            principal_id="__shared__",
            session_id="s",
            layer="semantic_shared",
            kind="explicit_memory",
            content="shared note",
            fingerprint=fingerprint_text("shared note"),
            source="test",
            importance=0.9,
        )
        rows = store.search_exact(
            profile_id="p",
            workspace_id="w",
            principal_id="__shared__",
            session_id="",
            layer="semantic_shared",
            limit=10,
        )
        assert rows[0]["user_id"] == ""
        assert rows[0]["user_email"] == ""
        assert rows[0]["user_name"] == ""
    finally:
        store.close()


def test_bootstrap_adds_identity_columns_to_legacy_db(tmp_path: Path) -> None:
    db_path = tmp_path / "memory.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE memories (
            id TEXT PRIMARY KEY,
            profile_id TEXT NOT NULL,
            workspace_id TEXT NOT NULL,
            principal_id TEXT NOT NULL,
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
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        """
    )
    conn.execute(
        """
        INSERT INTO memories (
            id, profile_id, workspace_id, principal_id, session_id, layer, kind,
            content, fingerprint, source, created_at, updated_at
        ) VALUES (
            'legacy', 'p', 'w', 'user-123', 's', 'semantic_user', 'explicit_memory',
            'old note', 'fp', 'seed', '2020-01-01T00:00:00+00:00',
            '2020-01-01T00:00:00+00:00'
        )
        """
    )
    conn.commit()
    conn.close()

    store = SQLiteStore(db_path, dimensions=16, index_path=tmp_path / "lancedb")
    store.bootstrap()
    try:
        probe = sqlite3.connect(db_path)
        columns = {row[1] for row in probe.execute("PRAGMA table_info(memories)")}
        probe.close()
        assert {"user_id", "user_email", "user_name"} <= columns

        rows = store.search_exact(
            profile_id="p",
            workspace_id="w",
            principal_id="user-123",
            session_id="",
            layer="semantic_user",
            limit=10,
        )
        # Legacy row recalled; identity columns default to ''.
        assert rows[0]["content"] == "old note"
        assert rows[0]["user_email"] == ""
    finally:
        store.close()
