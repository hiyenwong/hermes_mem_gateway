from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from plugins.memory.layered_lancedb_sqlite.cli import register_cli, run_cli
from plugins.memory.layered_lancedb_sqlite.config import ProviderConfig, save_config
from plugins.memory.layered_lancedb_sqlite.governance import fingerprint_text
from plugins.memory.layered_lancedb_sqlite.maintenance_service import (
    OPERATION_DAILY_COMPACTION,
    compact_daily,
    compact_user_day,
    maintenance_namespace,
    maintenance_state_key,
)
from plugins.memory.layered_lancedb_sqlite.policy import (
    maintenance_user_write_decision,
    resolve_shared_intent,
)
from plugins.memory.layered_lancedb_sqlite.storage import SQLiteStore


def today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def build_store(tmp_path: Path, config: ProviderConfig) -> SQLiteStore:
    base = config.storage_base(str(tmp_path))
    store = SQLiteStore(base / "memory.sqlite3", dimensions=config.embedding_dimensions, index_path=base / "lancedb")
    store.bootstrap()
    return store


def insert_user_memory(store: SQLiteStore, config: ProviderConfig, principal: str, content: str) -> str:
    return store.insert_memory(
        profile_id=config.profile_id,
        workspace_id=config.memory_workspace,
        principal_id=principal,
        session_id="session-1",
        layer="semantic_user",
        kind="explicit_memory",
        content=content,
        fingerprint=fingerprint_text(content),
        source="test",
        importance=0.95,
    )


def test_compact_user_day_preserves_principal_isolation(tmp_path: Path) -> None:
    config = ProviderConfig(profile_id="coder", memory_workspace="workspace-a", embedding_dimensions=32)
    store = build_store(tmp_path, config)
    try:
        date = today_utc()
        insert_user_memory(store, config, "user-a", "Remember that I prefer dark roast coffee.")
        insert_user_memory(store, config, "user-b", "Remember that I prefer jasmine tea.")

        result = compact_user_day(store=store, config=config, date=date, user_id="user-a")

        assert result.status == "completed"
        assert result.principal_id == "user-a"
        with sqlite3.connect(store.db_path) as conn:
            rows = conn.execute(
                "SELECT principal_id, layer, kind, content FROM memories WHERE source = ? ORDER BY principal_id",
                (OPERATION_DAILY_COMPACTION,),
            ).fetchall()
        assert rows == [
            (
                "user-a",
                "semantic_user",
                "daily_compaction_summary",
                "Daily memory maintenance summary for "
                + date
                + ":\n1. Remember that I prefer dark roast coffee.",
            )
        ]
    finally:
        store.close()


def test_compact_user_day_is_idempotent_and_failed_jobs_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = ProviderConfig(profile_id="coder", memory_workspace="workspace-a", embedding_dimensions=32)
    store = build_store(tmp_path, config)
    try:
        date = today_utc()
        insert_user_memory(store, config, "user-a", "Remember that I prefer espresso.")

        original_fetch = store.fetch_user_records_for_date

        def fail_once(**kwargs):
            raise RuntimeError("temporary maintenance failure")

        monkeypatch.setattr(store, "fetch_user_records_for_date", fail_once)
        with pytest.raises(RuntimeError):
            compact_user_day(store=store, config=config, date=date, user_id="user-a")

        key = maintenance_state_key(
            operation=OPERATION_DAILY_COMPACTION,
            profile_id="coder",
            workspace_id="workspace-a",
            principal_id="user-a",
            date=date,
        )
        assert store.get_maintenance_state(key)["status"] == "failed"

        monkeypatch.setattr(store, "fetch_user_records_for_date", original_fetch)
        first = compact_user_day(store=store, config=config, date=date, user_id="user-a")
        second = compact_user_day(store=store, config=config, date=date, user_id="user-a")

        assert first.status == "completed"
        assert second.skipped is True
        assert second.output_memory_id == first.output_memory_id
        with sqlite3.connect(store.db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE source = ? AND principal_id = ?",
                (OPERATION_DAILY_COMPACTION, "user-a"),
            ).fetchone()[0]
        assert count == 1
    finally:
        store.close()


def test_compact_daily_enumerates_user_principals(tmp_path: Path) -> None:
    config = ProviderConfig(profile_id="coder", memory_workspace="workspace-a", embedding_dimensions=32)
    store = build_store(tmp_path, config)
    try:
        date = today_utc()
        insert_user_memory(store, config, "a@example.com", "Remember that I prefer green tea.")
        insert_user_memory(store, config, "user-b", "Remember that I prefer black tea.")

        result = compact_daily(store=store, config=config, date=date)

        assert result["processed_principals"] == 2
        assert result["completed"] == 2
        assert result["failed"] == 0
    finally:
        store.close()


def test_maintenance_policy_allows_same_principal_and_blocks_cross_principal_or_shared() -> None:
    config = ProviderConfig(profile_id="coder", memory_workspace="workspace-a")
    namespace = maintenance_namespace(
        config,
        session_id="maintenance:2026-05-28:user-a",
        user_id="user-a",
    )

    same = maintenance_user_write_decision(namespace, target_principal_id="user-a")
    cross = maintenance_user_write_decision(namespace, target_principal_id="user-b")

    assert same.allowed is True
    assert same.layer == "semantic_user"
    assert same.reason == "maintenance_same_principal_user"
    assert cross.allowed is False
    assert cross.reason == "maintenance_cross_principal_blocked"


def test_maintenance_namespace_rejects_display_name_only() -> None:
    config = ProviderConfig(profile_id="coder", memory_workspace="workspace-a")

    with pytest.raises(ValueError):
        maintenance_namespace(config, session_id="maintenance:today:Doris", user_name="Doris")


def test_compact_daily_does_not_double_count_skipped_as_completed(tmp_path: Path) -> None:
    config = ProviderConfig(profile_id="coder", memory_workspace="workspace-a", embedding_dimensions=32)
    store = build_store(tmp_path, config)
    try:
        date = today_utc()
        insert_user_memory(store, config, "user-a", "Remember that I drink oolong.")

        first = compact_daily(store=store, config=config, date=date)
        second = compact_daily(store=store, config=config, date=date)

        assert first["completed"] == 1
        assert first["skipped"] == 0
        assert second["completed"] == 0
        assert second["skipped"] == 1
        assert second["completed"] + second["failed"] + second["skipped"] == second["processed_principals"]
    finally:
        store.close()


def test_compact_daily_uses_principal_source_over_at_sign_heuristic(tmp_path: Path) -> None:
    config = ProviderConfig(profile_id="coder", memory_workspace="workspace-a", embedding_dimensions=32)
    store = build_store(tmp_path, config)
    try:
        date = today_utc()
        oidc_subject = "auth0|abc@def"
        store.insert_memory(
            profile_id=config.profile_id,
            workspace_id=config.memory_workspace,
            principal_id=oidc_subject,
            session_id="session-1",
            layer="semantic_user",
            kind="explicit_memory",
            content="Remember that I prefer matcha.",
            fingerprint=fingerprint_text("Remember that I prefer matcha."),
            source="test",
            importance=0.95,
            metadata={"principal_source": "user_id"},
        )

        result = compact_daily(store=store, config=config, date=date)

        assert result["completed"] == 1
        assert result["failed"] == 0
        assert result["results"][0]["principal_id"] == oidc_subject
    finally:
        store.close()


def test_shared_intent_matches_chinese_phrase_in_natural_text() -> None:
    chinese_intent = resolve_shared_intent("请保存为共享记忆，让其他人也能用", None)
    english_intent = resolve_shared_intent("Please save this to shared memory now.", None)
    unrelated_intent = resolve_shared_intent("今天天气很好", None)

    assert chinese_intent.requested is True
    assert chinese_intent.source == "natural_language"
    assert english_intent.requested is True
    assert unrelated_intent.requested is False


def test_cli_compact_user_and_compact_daily(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    save_config(
        {
            "profile_id": "coder",
            "memory_workspace": "workspace-a",
            "embedding_dimensions": 32,
        },
        str(tmp_path),
    )
    config = ProviderConfig(profile_id="coder", memory_workspace="workspace-a", embedding_dimensions=32)
    store = build_store(tmp_path, config)
    date = today_utc()
    try:
        insert_user_memory(store, config, "cli-user", "Remember that I prefer CLI tests.")
    finally:
        store.close()

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    register_cli(subparsers)

    args = parser.parse_args(
        [
            "compact-user",
            "--profile",
            "coder",
            "--workspace",
            "workspace-a",
            "--date",
            date,
            "--user-id",
            "cli-user",
        ]
    )
    assert run_cli(args, str(tmp_path)) == 0
    compact_user_output = json.loads(capsys.readouterr().out)
    assert compact_user_output["status"] == "completed"
    assert compact_user_output["principal_id"] == "cli-user"

    args = parser.parse_args(
        [
            "compact-daily",
            "--profile",
            "coder",
            "--workspace",
            "workspace-a",
            "--date",
            date,
        ]
    )
    assert run_cli(args, str(tmp_path)) == 0
    compact_daily_output = json.loads(capsys.readouterr().out)
    assert compact_daily_output["processed_principals"] >= 1
    assert "completed" in compact_daily_output
