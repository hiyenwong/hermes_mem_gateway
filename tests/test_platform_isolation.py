from __future__ import annotations

import sqlite3
from pathlib import Path

from plugins.memory.layered_lancedb_sqlite import LayeredLanceDBSQLiteMemoryProvider
from plugins.memory.layered_lancedb_sqlite.storage import SQLiteStore


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


def _sqlite_path(tmp_path: Path) -> Path:
    return (
        tmp_path
        / "memory-providers/layered_lancedb_sqlite/coder/workspace-a/memory.sqlite3"
    )


def test_hermes_headers_become_private_principal_with_arbitrary_platform(
    tmp_path: Path,
) -> None:
    # platform is an arbitrary value NOT in the gateway allowlist, supplied only
    # via the X-Hermes-Platform header. The request must still be isolated.
    provider = build_provider(
        tmp_path,
        headers={
            "X-Hermes-User-Id": "user_001",
            "X-Hermes-User-Name": "张三",
            "X-Hermes-User-Email": "zhangsan@example.com",
            "X-Hermes-Platform": "wechat_miniprogram",
        },
    )
    assert provider._namespace.is_gateway is True
    assert provider._namespace.principal_id == "zhangsan@example.com"
    assert provider._namespace.platform == "wechat_miniprogram"

    provider.sync_turn("Remember that I prefer dark roast coffee beans.", "Noted.")
    provider.shutdown()

    with sqlite3.connect(_sqlite_path(tmp_path)) as conn:
        rows = conn.execute(
            "SELECT principal_id, platform, layer FROM memories WHERE layer = 'semantic_user'"
        ).fetchall()
    assert rows
    assert all(row[0] == "zhangsan@example.com" for row in rows)
    assert all(row[1] == "wechat_miniprogram" for row in rows)


def test_hermes_user_id_only_platform_from_header_isolates_user(
    tmp_path: Path,
) -> None:
    provider = build_provider(
        tmp_path,
        headers={
            "X-Hermes-User-Id": "user_001",
            "X-Hermes-Platform": "wechat_miniprogram",
        },
    )
    assert provider._namespace.is_gateway is True
    assert provider._namespace.principal_id == "user_001"
    provider.shutdown()


def test_hermes_headers_are_case_insensitive(tmp_path: Path) -> None:
    provider = build_provider(
        tmp_path,
        headers={
            "x-hermes-user-id": "user_001",
            "X-HERMES-PLATFORM": "WeChat",
        },
    )
    assert provider._namespace.principal_id == "user_001"
    # Header value casing is preserved (platforms are case-sensitive values).
    assert provider._namespace.platform == "WeChat"
    provider.shutdown()


def test_hermes_headers_take_priority_over_openwebui(tmp_path: Path) -> None:
    provider = build_provider(
        tmp_path,
        platform="gateway",
        headers={
            "X-Hermes-User-Email": "hermes@example.com",
            "X-OpenWebUI-User-Email": "owui@example.com",
        },
    )
    assert provider._namespace.principal_id == "hermes@example.com"
    provider.shutdown()


def test_platform_is_recorded_on_shared_cli_memory(tmp_path: Path) -> None:
    provider = build_provider(tmp_path, platform="cli")
    provider.sync_turn(
        "Remember that the deployment window is Fridays at 5 PM UTC.", "Stored."
    )
    provider.shutdown()

    with sqlite3.connect(_sqlite_path(tmp_path)) as conn:
        rows = conn.execute(
            "SELECT platform FROM memories WHERE layer = 'semantic_shared'"
        ).fetchall()
    assert rows
    assert all(row[0] == "cli" for row in rows)


def test_same_user_memory_is_unified_across_platforms_by_default(
    tmp_path: Path,
) -> None:
    provider = build_provider(tmp_path, user_id="user_001", platform="wechat")
    provider.sync_turn("Remember that I prefer dark roast coffee beans.", "Noted.")
    provider.shutdown()

    provider = build_provider(tmp_path, user_id="user_001", platform="slack")
    provider.sync_turn("Remember that my favorite color is teal.", "Noted.")
    # Default config: cross-platform unified recall for the same user.
    recall = provider.prefetch("coffee")
    assert "dark roast coffee" in recall
    provider.shutdown()


def test_platform_scoped_recall_restricts_to_current_platform(tmp_path: Path) -> None:
    overrides = {"recall_platform_scoped": True}
    provider = build_provider(
        tmp_path, user_id="user_001", platform="wechat", config_overrides=overrides
    )
    provider.sync_turn("Remember that I prefer dark roast coffee beans.", "Noted.")
    provider.shutdown()

    provider = build_provider(
        tmp_path, user_id="user_001", platform="slack", config_overrides=overrides
    )
    provider.sync_turn("Remember that my favorite color is teal.", "Noted.")
    # Coffee was written on wechat; slack-scoped recall must not see it.
    assert "dark roast coffee" not in provider.prefetch("coffee")
    # The slack memory is recallable on slack.
    assert "favorite color is teal" in provider.prefetch("color")
    provider.shutdown()


def test_bootstrap_adds_platform_column_to_legacy_db(tmp_path: Path) -> None:
    base = tmp_path / "legacy"
    base.mkdir(parents=True, exist_ok=True)
    db_path = base / "memory.sqlite3"
    # Create a legacy memories table WITHOUT the platform column.
    with sqlite3.connect(db_path) as conn:
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
                last_accessed_at TEXT,
                archived_at TEXT,
                supersedes_id TEXT,
                superseded_by_id TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );
            """
        )

    store = SQLiteStore(db_path, dimensions=32, index_path=base / "lancedb")
    store.bootstrap()
    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(memories)")}
    assert "platform" in columns

    # Inserts carrying a platform value succeed against the migrated table.
    store.insert_memory(
        profile_id="p",
        workspace_id="w",
        principal_id="user_001",
        session_id="s",
        layer="episodic",
        kind="turn",
        content="hello",
        fingerprint="fp",
        source="test",
        importance=0.5,
        platform="wechat_miniprogram",
    )
    store.close()
    with sqlite3.connect(db_path) as conn:
        platform = conn.execute("SELECT platform FROM memories").fetchone()[0]
    assert platform == "wechat_miniprogram"


def test_backfill_platform_from_provenance(tmp_path: Path) -> None:
    base = tmp_path / "backfill"
    store = SQLiteStore(
        base / "memory.sqlite3", dimensions=32, index_path=base / "lancedb"
    )
    store.bootstrap()

    # Simulate a legacy memory whose platform column is empty but whose
    # provenance preserved the real platform.
    recoverable = store.insert_memory(
        profile_id="p",
        workspace_id="w",
        principal_id="user_001",
        session_id="s",
        layer="episodic",
        kind="turn",
        content="recoverable",
        fingerprint="fp1",
        source="test",
        importance=0.5,
        platform="",
    )
    store.add_provenance(
        recoverable, source_type="sync_turn", platform="wechat_miniprogram"
    )
    # A memory with no platform anywhere — cannot be recovered.
    store.insert_memory(
        profile_id="p",
        workspace_id="w",
        principal_id="user_002",
        session_id="s",
        layer="episodic",
        kind="turn",
        content="unrecoverable",
        fingerprint="fp2",
        source="test",
        importance=0.5,
        platform="",
    )

    dry = store.backfill_platform_from_provenance(dry_run=True)
    assert dry["empty_before"] == 2
    assert dry["fillable"] == 1
    assert dry["updated"] == 0

    applied = store.backfill_platform_from_provenance(dry_run=False)
    assert applied["updated"] == 1
    assert applied["remaining_empty"] == 1

    with sqlite3.connect(base / "memory.sqlite3") as conn:
        rows = dict(conn.execute("SELECT content, platform FROM memories").fetchall())
    store.close()
    assert rows["recoverable"] == "wechat_miniprogram"
    assert rows["unrecoverable"] == ""


def test_index_rebuilds_when_embedder_version_changes(tmp_path: Path) -> None:
    base = tmp_path / "rebuild"
    store = SQLiteStore(
        base / "memory.sqlite3", dimensions=32, index_path=base / "lancedb"
    )
    store.bootstrap()
    store.ensure_index_current()
    # Simulate a DB written by an older embedder version.
    store.set_maintenance_state(
        "embedder_state", {"version": "blake2b-counts-v1", "dimensions": 32}
    )
    result = store.ensure_index_current()
    store.close()
    assert result["rebuilt"] is True
    assert result["version"] == "blake2b-counts-v2"
