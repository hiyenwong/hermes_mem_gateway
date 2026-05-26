from __future__ import annotations

import sqlite3
from pathlib import Path

from plugins.memory.layered_lancedb_sqlite import LayeredLanceDBSQLiteMemoryProvider


def build_provider(tmp_path: Path, *, session_id: str = "session-1", **kwargs) -> LayeredLanceDBSQLiteMemoryProvider:
    provider = LayeredLanceDBSQLiteMemoryProvider()
    provider.save_config(
        {
            "memory_workspace": "workspace-a",
            "profile_id": "coder",
            "embedding_dimensions": 32,
        },
        str(tmp_path),
    )
    provider.initialize(
        session_id,
        hermes_home=str(tmp_path),
        agent_identity="coder",
        agent_workspace="workspace-a",
        **kwargs,
    )
    return provider


def test_gateway_user_scope_blocks_unstable_identity_and_isolates_user_semantic(tmp_path: Path) -> None:
    provider = build_provider(tmp_path, platform="gateway", user_id="user-1")
    provider.sync_turn("Remember that I prefer dark roast coffee beans.", "Noted.")
    provider.shutdown()

    provider = build_provider(tmp_path, platform="gateway", user_id="user-1")
    recall = provider.prefetch("coffee")
    assert "dark roast coffee" in recall
    provider.shutdown()

    provider = build_provider(tmp_path, platform="gateway", user_id="user-2")
    recall = provider.prefetch("coffee")
    assert "dark roast coffee" not in recall
    provider.shutdown()

    provider = build_provider(tmp_path, platform="gateway", user_id="")
    provider.sync_turn("Remember that I prefer jasmine tea.", "Noted.")
    provider.shutdown()

    sqlite_path = tmp_path / "memory-providers/layered_lancedb_sqlite/coder/workspace-a/memory.sqlite3"
    with sqlite3.connect(sqlite_path) as conn:
        rows = conn.execute("SELECT layer, principal_id, content FROM memories WHERE layer LIKE 'semantic%'").fetchall()
    assert any(row[0] == "semantic_user" and row[1] == "user-1" for row in rows)
    assert not any("jasmine tea" in row[2] and row[0] == "semantic_user" for row in rows)


def test_non_gateway_shared_recall_and_session_switch_rotation(tmp_path: Path) -> None:
    provider = build_provider(tmp_path, platform="cli")
    provider.sync_turn("Remember that the deployment window is Fridays at 5 PM UTC.", "Will remember.")
    provider.on_session_switch("session-2", reset=True, platform="cli")
    provider.sync_turn("This is only temporary for this session.", "Okay.")
    recall = provider.prefetch("deployment window")
    assert "deployment window is Fridays" in recall
    assert "temporary for this session" in recall
    provider.on_session_switch("session-3", reset=True, platform="cli")
    recall = provider.prefetch("temporary")
    assert "temporary for this session" not in recall
    provider.shutdown()


def test_non_primary_context_cannot_promote_durable_memory(tmp_path: Path) -> None:
    provider = build_provider(tmp_path, platform="gateway", user_id="user-1", agent_context="subagent")
    provider.sync_turn("Remember that my legal name is Alicia Example.", "Noted.")
    provider.shutdown()

    sqlite_path = tmp_path / "memory-providers/layered_lancedb_sqlite/coder/workspace-a/memory.sqlite3"
    with sqlite3.connect(sqlite_path) as conn:
        rows = conn.execute("SELECT layer FROM memories").fetchall()
    assert rows
    assert all(row[0] == "episodic" for row in rows)


def test_non_primary_memory_write_does_not_create_shared_durable_memory(tmp_path: Path) -> None:
    provider = build_provider(tmp_path, platform="cli", agent_context="subagent")
    provider.on_memory_write("add", "memory", "The team deploys from a restricted jump host.")
    provider.shutdown()

    sqlite_path = tmp_path / "memory-providers/layered_lancedb_sqlite/coder/workspace-a/memory.sqlite3"
    with sqlite3.connect(sqlite_path) as conn:
        rows = conn.execute("SELECT layer FROM memories WHERE layer LIKE 'semantic%'").fetchall()
    assert rows == []


def test_index_rebuild_and_builtin_memory_mirroring(tmp_path: Path) -> None:
    provider = build_provider(tmp_path, platform="cli")
    provider.on_memory_write("add", "memory", "The project uses uv for Python packaging.", {"write_origin": "builtin"})
    provider.shutdown()

    provider = build_provider(tmp_path, platform="cli")
    validate = provider.validate_storage()
    assert validate["memory_count"] >= 1
    base = tmp_path / "memory-providers/layered_lancedb_sqlite/coder/workspace-a/lancedb"
    stub_index = base / "semantic_index.json"
    if stub_index.exists():
        stub_index.unlink()
    rebuilt = provider.rebuild_index()
    assert rebuilt >= 1
    recall = provider.prefetch("uv packaging")
    assert "uv for Python packaging" in recall
    provider.shutdown()


def test_supersession_replaces_older_shared_memory(tmp_path: Path) -> None:
    provider = build_provider(tmp_path, platform="cli")
    provider.sync_turn("Remember that the API base URL is https://api-v1.internal.example.", "Stored.")
    provider.sync_turn("Remember that the API base URL is https://api.internal.example.", "Updated.")
    provider.shutdown()

    sqlite_path = tmp_path / "memory-providers/layered_lancedb_sqlite/coder/workspace-a/memory.sqlite3"
    with sqlite3.connect(sqlite_path) as conn:
        rows = conn.execute(
            "SELECT content, status, supersedes_id, superseded_by_id FROM memories WHERE layer = 'semantic_shared' ORDER BY created_at"
        ).fetchall()
    assert len(rows) == 2
    assert rows[0][1] == "superseded"
    assert rows[1][2] is not None


def test_prefetch_cache_is_scoped_by_principal(tmp_path: Path) -> None:
    provider = build_provider(tmp_path, platform="gateway", user_id="user-1")
    provider.sync_turn("Remember that I prefer dark roast coffee beans.", "Noted.")
    provider.shutdown()

    provider = build_provider(tmp_path, platform="gateway", user_id="user-1")
    recall_user_1 = provider.prefetch("coffee")
    assert "dark roast coffee" in recall_user_1
    provider.on_session_switch("session-1", platform="gateway", user_id="user-2")
    recall_user_2 = provider.prefetch("coffee")
    assert "dark roast coffee" not in recall_user_2
    provider.shutdown()
