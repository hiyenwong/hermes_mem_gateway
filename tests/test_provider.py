from __future__ import annotations

import sqlite3
from pathlib import Path

from plugins.memory.layered_lancedb_sqlite import LayeredLanceDBSQLiteMemoryProvider


def build_provider(
    tmp_path: Path,
    *,
    session_id: str = "session-1",
    config_overrides: dict[str, object] | None = None,
    **kwargs,
) -> LayeredLanceDBSQLiteMemoryProvider:
    provider = LayeredLanceDBSQLiteMemoryProvider()
    config = {
        "memory_workspace": "workspace-a",
        "profile_id": "coder",
        "embedding_dimensions": 32,
    }
    config.update(config_overrides or {})
    provider.save_config(config, str(tmp_path))
    provider.initialize(
        session_id,
        hermes_home=str(tmp_path),
        agent_identity="coder",
        agent_workspace="workspace-a",
        **kwargs,
    )
    return provider


def write_env(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"{key}={value}" for key, value in values.items()) + "\n")


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


def test_chinese_explicit_memory_promotes_to_semantic_user(tmp_path: Path) -> None:
    provider = build_provider(tmp_path, platform="gateway", user_id="user-zh")
    provider.sync_turn("请记住，我的项目用 uv 做包管理。", "好的，已记下。")
    provider.shutdown()

    sqlite_path = tmp_path / "memory-providers/layered_lancedb_sqlite/coder/workspace-a/memory.sqlite3"
    with sqlite3.connect(sqlite_path) as conn:
        rows = conn.execute(
            "SELECT layer, principal_id, content FROM memories WHERE layer = 'semantic_user'"
        ).fetchall()
    assert any(row[1] == "user-zh" and "uv 做包管理" in row[2] for row in rows)


def test_recall_returns_today_other_session_episodic_for_gateway_user(tmp_path: Path) -> None:
    provider = build_provider(tmp_path, platform="gateway", user_id="user-x", session_id="session-old")
    provider.sync_turn("昨晚那场会议的纪要发到飞书共享文件夹了", "好的，知道了。")
    provider.shutdown()

    provider = build_provider(tmp_path, platform="gateway", user_id="user-x", session_id="session-new")
    recall = provider.prefetch("飞书")
    assert "Today's cross-session memory" in recall
    assert "飞书共享文件夹" in recall
    provider.shutdown()


def test_recall_other_session_scope_excludes_current_session(tmp_path: Path) -> None:
    provider = build_provider(tmp_path, platform="gateway", user_id="user-y", session_id="session-only")
    provider.sync_turn("当前 session 里随便说点东西", "OK。")
    recall = provider.prefetch("session")
    assert "Today's cross-session memory" not in recall
    provider.shutdown()


def test_explicit_session_id_is_honored_before_session_switch(tmp_path: Path) -> None:
    provider = build_provider(tmp_path, platform="cli", session_id="session-1")
    provider.sync_turn(
        "Remember that session two owns the release checklist.",
        "Stored.",
        session_id="session-2",
    )
    recall_session_2 = provider.prefetch("release checklist", session_id="session-2")
    recall_session_1 = provider.prefetch("release checklist", session_id="session-1")
    assert "session two owns the release checklist" in recall_session_2
    assert "session two owns the release checklist" not in recall_session_1
    provider.shutdown()


def test_hermes_home_env_can_define_memory_workspace(tmp_path: Path) -> None:
    write_env(tmp_path / ".env", {"LAYERED_MEMORY_WORKSPACE": "workspace-home-env"})

    provider = LayeredLanceDBSQLiteMemoryProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), agent_identity="coder", agent_workspace="")
    try:
        assert provider._namespace.workspace_id == "workspace-home-env"
    finally:
        provider.shutdown()


def test_profile_env_overrides_hermes_home_env(tmp_path: Path) -> None:
    write_env(tmp_path / ".env", {"LAYERED_MEMORY_WORKSPACE": "workspace-home-env"})
    write_env(
        tmp_path / "profiles" / "coder" / ".env",
        {"LAYERED_MEMORY_WORKSPACE": "workspace-profile-env"},
    )

    provider = LayeredLanceDBSQLiteMemoryProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), agent_identity="coder", agent_workspace="")
    try:
        assert provider._namespace.workspace_id == "workspace-profile-env"
    finally:
        provider.shutdown()


def test_runtime_agent_workspace_overrides_env_workspace(tmp_path: Path) -> None:
    write_env(tmp_path / ".env", {"LAYERED_MEMORY_WORKSPACE": "workspace-home-env"})
    write_env(
        tmp_path / "profiles" / "coder" / ".env",
        {"LAYERED_MEMORY_WORKSPACE": "workspace-profile-env"},
    )

    provider = LayeredLanceDBSQLiteMemoryProvider()
    provider.initialize(
        "session-1",
        hermes_home=str(tmp_path),
        agent_identity="coder",
        agent_workspace="workspace-runtime",
    )
    try:
        assert provider._namespace.workspace_id == "workspace-runtime"
    finally:
        provider.shutdown()


def test_openwebui_email_header_becomes_private_principal(tmp_path: Path) -> None:
    provider = build_provider(
        tmp_path,
        platform="gateway",
        headers={
            "X-OpenWebUI-User-Email": "doris@example.com",
            "X-OpenWebUI-User-Name": "Doris",
        },
    )
    provider.sync_turn("Remember that I prefer jasmine tea.", "Stored.")
    provider.shutdown()

    sqlite_path = tmp_path / "memory-providers/layered_lancedb_sqlite/coder/workspace-a/memory.sqlite3"
    with sqlite3.connect(sqlite_path) as conn:
        rows = conn.execute(
            "SELECT principal_id, layer FROM memories WHERE layer = 'semantic_user'"
        ).fetchall()
    assert rows == [("doris@example.com", "semantic_user")]


def test_openwebui_user_id_fallback_does_not_use_display_name(tmp_path: Path) -> None:
    provider = build_provider(
        tmp_path,
        platform="gateway",
        headers={
            "X-OpenWebUI-User-Id": "owui-user-42",
            "X-OpenWebUI-User-Name": "Doris",
        },
    )
    provider.sync_turn("Remember that I prefer oolong tea.", "Stored.")
    provider.shutdown()

    sqlite_path = tmp_path / "memory-providers/layered_lancedb_sqlite/coder/workspace-a/memory.sqlite3"
    with sqlite3.connect(sqlite_path) as conn:
        rows = conn.execute(
            "SELECT principal_id FROM memories WHERE layer = 'semantic_user'"
        ).fetchall()
    assert rows == [("owui-user-42",)]
    assert all(row[0] != "Doris" for row in rows)


def test_gateway_shared_request_without_allowlist_stays_private(tmp_path: Path) -> None:
    provider = build_provider(
        tmp_path,
        platform="gateway",
        headers={"X-OpenWebUI-User-Email": "user@example.com"},
        request_metadata={"shared_memory": True},
    )
    provider.sync_turn("Remember this as shared: the project uses uv.", "Stored.")
    provider.shutdown()

    sqlite_path = tmp_path / "memory-providers/layered_lancedb_sqlite/coder/workspace-a/memory.sqlite3"
    with sqlite3.connect(sqlite_path) as conn:
        rows = conn.execute(
            "SELECT principal_id, layer FROM memories WHERE layer LIKE 'semantic_%' ORDER BY layer"
        ).fetchall()
    assert rows == [("user@example.com", "semantic_user")]


def test_allowlisted_gateway_user_can_write_shared_via_metadata(tmp_path: Path) -> None:
    provider = build_provider(
        tmp_path,
        platform="gateway",
        headers={
            "X-OpenWebUI-User-Email": "admin@example.com",
            "X-OpenWebUI-User-Name": "Admin Doris",
        },
        request_metadata={"shared_memory": True},
        config_overrides={"shared_writer_emails": ["admin@example.com"]},
    )
    provider.sync_turn("Remember that the shared deployment checklist lives in Notion.", "Stored.")
    recall = provider.prefetch("deployment checklist")
    provider.shutdown()

    sqlite_path = tmp_path / "memory-providers/layered_lancedb_sqlite/coder/workspace-a/memory.sqlite3"
    with sqlite3.connect(sqlite_path) as conn:
        memory_rows = conn.execute(
            "SELECT principal_id, layer, metadata_json FROM memories WHERE layer = 'semantic_shared'"
        ).fetchall()
        provenance_rows = conn.execute(
            "SELECT metadata_json FROM provenance WHERE source_type = 'promotion'"
        ).fetchall()
    assert len(memory_rows) == 1
    assert memory_rows[0][0] == "__shared__"
    assert '"shared_authorized": true' in memory_rows[0][2]
    assert provenance_rows and '"shared_request_source": "metadata"' in provenance_rows[0][0]
    assert "display_name: Admin Doris" in recall
    assert "X-OpenWebUI-User-Email" not in recall


def test_metadata_shared_intent_overrides_natural_language_shared_request(tmp_path: Path) -> None:
    provider = build_provider(
        tmp_path,
        platform="gateway",
        headers={"X-OpenWebUI-User-Email": "admin@example.com"},
        request_metadata={"shared_memory": False},
        config_overrides={"shared_writer_emails": ["admin@example.com"]},
    )
    provider.sync_turn("Remember this as shared: the staging API base URL is https://api.internal.example.", "Stored.")
    provider.shutdown()

    sqlite_path = tmp_path / "memory-providers/layered_lancedb_sqlite/coder/workspace-a/memory.sqlite3"
    with sqlite3.connect(sqlite_path) as conn:
        rows = conn.execute(
            "SELECT principal_id, layer, metadata_json FROM memories WHERE layer LIKE 'semantic_%'"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "admin@example.com"
    assert rows[0][1] == "semantic_user"
    assert '"shared_request_source": "metadata"' in rows[0][2]
    assert '"shared_authorized": false' in rows[0][2]
