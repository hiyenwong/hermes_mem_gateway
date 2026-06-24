"""Tests for the expires_at memory expiry feature (v0.4.0).

Covers:
- Column migration: old DB (no expires_at) → bootstrap adds it; old memories
  remain recallable.
- Recall filtering: expired → excluded; future/empty → included.
- purge_expired CLI method: dry-run vs --apply.
- Deterministic on the stub backend (monkeypatch lancedb to None).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from plugins.memory.layered_lancedb_sqlite.storage import SQLiteStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _store(tmp_path: Path) -> SQLiteStore:
    base = tmp_path / "mem"
    store = SQLiteStore(
        base / "memory.sqlite3",
        dimensions=32,
        index_path=base / "lancedb",
    )
    store.bootstrap()
    return store


def _insert(store: SQLiteStore, *, content: str, expires_at: str = "") -> str:
    return store.insert_memory(
        profile_id="coder",
        workspace_id="workspace-a",
        principal_id="user-1",
        session_id="session-1",
        layer="semantic_user",
        kind="builtin_memory",
        content=content,
        fingerprint=f"fp-{content}",
        source="test",
        importance=0.9,
        platform="gateway",
        expires_at=expires_at,
    )


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ---------------------------------------------------------------------------
# Migration: old DB without expires_at column
# ---------------------------------------------------------------------------


def test_migration_adds_expires_at_column_to_old_db(tmp_path: Path) -> None:
    base = tmp_path / "old"
    db_path = base / "memory.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Create a DB that predates the expires_at column.
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE memories (
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
            CREATE TABLE provenance (
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
            CREATE TABLE maintenance_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO memories (
                id, profile_id, workspace_id, principal_id, session_id, layer,
                kind, content, fingerprint, source, created_at, updated_at
            ) VALUES (
                'legacy-1', 'coder', 'workspace-a', 'user-1', 'session-1',
                'semantic_user', 'builtin_memory', 'legacy content',
                'fp-legacy', 'test', '2026-01-01T00:00:00+00:00',
                '2026-01-01T00:00:00+00:00'
            );
            """
        )

    # Bootstrap with the new code — should add expires_at via _ensure_column.
    store = SQLiteStore(
        db_path,
        dimensions=32,
        index_path=base / "lancedb",
    )
    store.bootstrap()
    try:
        # Column now exists.
        with sqlite3.connect(db_path) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(memories)")}
        assert "expires_at" in cols

        # Legacy row recallable (expires_at defaults to '').
        records = store.fetch_existing_durable(
            profile_id="coder",
            workspace_id="workspace-a",
            principal_id="user-1",
            layer="semantic_user",
        )
        assert any(r["id"] == "legacy-1" for r in records)
        assert all(r["expires_at"] == "" for r in records)
    finally:
        store.close()


# ---------------------------------------------------------------------------
# Recall filtering
# ---------------------------------------------------------------------------


class TestExpiryFiltering:
    """Force the stub backend so tests are deterministic without LanceDB."""

    @pytest.fixture(autouse=True)
    def _force_stub(self, monkeypatch):
        monkeypatch.setattr(
            "plugins.memory.layered_lancedb_sqlite.storage.lancedb", None
        )
        monkeypatch.setattr("plugins.memory.layered_lancedb_sqlite.storage.pa", None)

    def test_expired_memory_excluded_from_fetch_existing_durable(
        self, tmp_path: Path
    ) -> None:
        store = _store(tmp_path)
        try:
            past = _iso(datetime.now(timezone.utc) - timedelta(hours=1))
            _insert(store, content="expired secret", expires_at=past)
            _insert(store, content="permanent note")

            records = store.fetch_existing_durable(
                profile_id="coder",
                workspace_id="workspace-a",
                principal_id="user-1",
                layer="semantic_user",
            )
            contents = [r["content"] for r in records]
            assert "permanent note" in contents
            assert "expired secret" not in contents
        finally:
            store.close()

    def test_expired_memory_excluded_from_search_exact(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        try:
            past = _iso(datetime.now(timezone.utc) - timedelta(hours=1))
            _insert(store, content="expired exact match", expires_at=past)
            _insert(store, content="live exact match")

            records = store.search_exact(
                profile_id="coder",
                workspace_id="workspace-a",
                principal_id="user-1",
                session_id="session-1",
                layer="semantic_user",
                limit=10,
                platform="gateway",
            )
            contents = [r["content"] for r in records]
            assert "live exact match" in contents
            assert "expired exact match" not in contents
        finally:
            store.close()

    def test_future_expiry_included_in_recall(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        try:
            future = _iso(datetime.now(timezone.utc) + timedelta(days=7))
            _insert(store, content="future expiry note", expires_at=future)

            records = store.fetch_existing_durable(
                profile_id="coder",
                workspace_id="workspace-a",
                principal_id="user-1",
                layer="semantic_user",
            )
            assert any(r["content"] == "future expiry note" for r in records)
        finally:
            store.close()

    def test_empty_expiry_always_included(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        try:
            _insert(store, content="never expires", expires_at="")
            records = store.fetch_existing_durable(
                profile_id="coder",
                workspace_id="workspace-a",
                principal_id="user-1",
                layer="semantic_user",
            )
            assert any(r["content"] == "never expires" for r in records)
        finally:
            store.close()

    def test_expired_excluded_from_eligible_index_rows(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        try:
            past = _iso(datetime.now(timezone.utc) - timedelta(hours=1))
            _insert(store, content="expired indexed", expires_at=past)
            _insert(store, content="live indexed")

            rows = store.eligible_index_rows()
            contents = [r["content"] for r in rows]
            assert "live indexed" in contents
            assert "expired indexed" not in contents
        finally:
            store.close()

    def test_expired_excluded_from_fetch_user_records_for_date(
        self, tmp_path: Path
    ) -> None:
        store = _store(tmp_path)
        try:
            past = _iso(datetime.now(timezone.utc) - timedelta(hours=1))
            _insert(store, content="expired daily", expires_at=past)
            _insert(store, content="live daily")

            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            records = store.fetch_user_records_for_date(
                profile_id="coder",
                workspace_id="workspace-a",
                principal_id="user-1",
                date=today,
            )
            contents = [r["content"] for r in records]
            assert "live daily" in contents
            assert "expired daily" not in contents
        finally:
            store.close()


# ---------------------------------------------------------------------------
# purge_expired
# ---------------------------------------------------------------------------


class TestPurgeExpired:
    @pytest.fixture(autouse=True)
    def _force_stub(self, monkeypatch):
        monkeypatch.setattr(
            "plugins.memory.layered_lancedb_sqlite.storage.lancedb", None
        )
        monkeypatch.setattr("plugins.memory.layered_lancedb_sqlite.storage.pa", None)

    def test_dry_run_reports_but_does_not_archive(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        try:
            past = _iso(datetime.now(timezone.utc) - timedelta(hours=1))
            _insert(store, content="expired-1", expires_at=past)
            _insert(store, content="live-1")

            result = store.purge_expired(dry_run=True)
            assert result["expired_count"] == 1
            assert result["purged"] == 0
            assert result["dry_run"] is True

            # Still active (not archived).
            with sqlite3.connect(tmp_path / "mem" / "memory.sqlite3") as conn:
                row = conn.execute(
                    "SELECT status FROM memories WHERE content = 'expired-1'"
                ).fetchone()
            assert row[0] == "active"
        finally:
            store.close()

    def test_apply_archives_expired(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        try:
            past = _iso(datetime.now(timezone.utc) - timedelta(hours=1))
            _insert(store, content="expired-2", expires_at=past)
            _insert(store, content="live-2")

            result = store.purge_expired(dry_run=False)
            assert result["expired_count"] == 1
            assert result["purged"] == 1
            assert result["dry_run"] is False

            with sqlite3.connect(tmp_path / "mem" / "memory.sqlite3") as conn:
                rows = conn.execute(
                    "SELECT content, status FROM memories ORDER BY content"
                ).fetchall()
            assert rows == [
                ("expired-2", "archived"),
                ("live-2", "active"),
            ]
        finally:
            store.close()


# ---------------------------------------------------------------------------
# Row dict carries expires_at
# ---------------------------------------------------------------------------


class TestExpiresAtInRowDict:
    @pytest.fixture(autouse=True)
    def _force_stub(self, monkeypatch):
        monkeypatch.setattr(
            "plugins.memory.layered_lancedb_sqlite.storage.lancedb", None
        )
        monkeypatch.setattr("plugins.memory.layered_lancedb_sqlite.storage.pa", None)

    def test_row_dict_contains_expires_at(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        try:
            future = _iso(datetime.now(timezone.utc) + timedelta(days=3))
            _insert(store, content="stamped", expires_at=future)

            records = store.fetch_existing_durable(
                profile_id="coder",
                workspace_id="workspace-a",
                principal_id="user-1",
                layer="semantic_user",
            )
            assert len(records) == 1
            assert records[0]["expires_at"] == future
        finally:
            store.close()
