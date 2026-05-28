from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from plugins.memory.layered_lancedb_sqlite.config import ProviderConfig
from plugins.memory.layered_lancedb_sqlite.governance import fingerprint_text
from plugins.memory.layered_lancedb_sqlite.storage import (
    EMBEDDER_STATE_KEY,
    EMBEDDER_VERSION,
    SemanticIndex,
    SQLiteStore,
    cosine_similarity,
    embed_text,
)


REPO_ROOT = Path(__file__).resolve().parent.parent


def _build_store(tmp_path: Path, config: ProviderConfig) -> SQLiteStore:
    base = config.storage_base(str(tmp_path))
    store = SQLiteStore(base / "memory.sqlite3", dimensions=config.embedding_dimensions, index_path=base / "lancedb")
    store.bootstrap()
    return store


def test_embed_text_is_process_independent() -> None:
    script = (
        "import json, sys\n"
        f"sys.path.insert(0, {str(REPO_ROOT)!r})\n"
        "from plugins.memory.layered_lancedb_sqlite.storage import embed_text\n"
        "print(json.dumps(embed_text('Hello layered memory provider', 16)))\n"
    )
    base_env = {**os.environ}
    base_env.pop("PYTHONHASHSEED", None)
    env_one = {**base_env, "PYTHONHASHSEED": "1"}
    env_two = {**base_env, "PYTHONHASHSEED": "424242"}
    one = subprocess.check_output([sys.executable, "-c", script], env=env_one)
    two = subprocess.check_output([sys.executable, "-c", script], env=env_two)
    in_process = embed_text("Hello layered memory provider", 16)

    assert json.loads(one) == json.loads(two) == in_process


def test_ensure_index_current_skips_rebuild_when_state_matches(tmp_path: Path) -> None:
    config = ProviderConfig(profile_id="coder", memory_workspace="workspace-a", embedding_dimensions=16)
    store = _build_store(tmp_path, config)
    try:
        store.insert_memory(
            profile_id=config.profile_id,
            workspace_id=config.memory_workspace,
            principal_id="user-a",
            session_id="session-1",
            layer="semantic_user",
            kind="explicit_memory",
            content="Remember oolong",
            fingerprint=fingerprint_text("Remember oolong"),
            source="test",
            importance=0.9,
        )
        first = store.ensure_index_current()
        second = store.ensure_index_current()

        assert first["rebuilt"] is True
        assert second["rebuilt"] is False
        assert second["version"] == EMBEDDER_VERSION
        assert second["dimensions"] == 16
    finally:
        store.close()


def test_ensure_index_current_rebuilds_on_dimension_change(tmp_path: Path) -> None:
    config_a = ProviderConfig(profile_id="coder", memory_workspace="workspace-a", embedding_dimensions=16)
    store_a = _build_store(tmp_path, config_a)
    try:
        store_a.insert_memory(
            profile_id=config_a.profile_id,
            workspace_id=config_a.memory_workspace,
            principal_id="user-a",
            session_id="session-1",
            layer="semantic_user",
            kind="explicit_memory",
            content="Remember matcha",
            fingerprint=fingerprint_text("Remember matcha"),
            source="test",
            importance=0.9,
        )
        store_a.ensure_index_current()
    finally:
        store_a.close()

    config_b = ProviderConfig(profile_id="coder", memory_workspace="workspace-a", embedding_dimensions=32)
    store_b = _build_store(tmp_path, config_b)
    try:
        result = store_b.ensure_index_current()
        assert result["rebuilt"] is True
        assert result["dimensions"] == 32
        state = store_b.get_maintenance_state(EMBEDDER_STATE_KEY)
        assert state == {"version": EMBEDDER_VERSION, "dimensions": 32}
    finally:
        store_b.close()


def test_cosine_similarity_raises_on_dimension_mismatch() -> None:
    with pytest.raises(ValueError):
        cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0])


def test_semantic_search_skips_rows_with_stale_vector_dimensions(tmp_path: Path) -> None:
    index = SemanticIndex(tmp_path / "lancedb", dimensions=16)
    fresh_vector = embed_text("matcha", 16)
    index.upsert(
        [
            {
                "memory_id": "fresh",
                "profile_id": "p",
                "workspace_id": "w",
                "principal_id": "user-a",
                "session_id": "s",
                "layer": "semantic_user",
                "kind": "explicit_memory",
                "status": "active",
                "content": "matcha",
                "vector": fresh_vector,
            },
            {
                "memory_id": "stale",
                "profile_id": "p",
                "workspace_id": "w",
                "principal_id": "user-a",
                "session_id": "s",
                "layer": "semantic_user",
                "kind": "explicit_memory",
                "status": "active",
                "content": "matcha",
                "vector": [0.1, 0.2, 0.3],
            },
        ]
    )
    results = index.search(
        "matcha",
        filters={"profile_id": "p", "workspace_id": "w", "principal_id": "user-a", "layer": "semantic_user"},
        limit=5,
    )
    memory_ids = [item.record["memory_id"] for item in results]
    assert "fresh" in memory_ids
    assert "stale" not in memory_ids


def test_ensure_index_current_rebuilds_on_version_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = ProviderConfig(profile_id="coder", memory_workspace="workspace-a", embedding_dimensions=16)
    store = _build_store(tmp_path, config)
    try:
        store.insert_memory(
            profile_id=config.profile_id,
            workspace_id=config.memory_workspace,
            principal_id="user-a",
            session_id="session-1",
            layer="semantic_user",
            kind="explicit_memory",
            content="Remember sencha",
            fingerprint=fingerprint_text("Remember sencha"),
            source="test",
            importance=0.9,
        )
        store.ensure_index_current()

        monkeypatch.setattr(
            "plugins.memory.layered_lancedb_sqlite.storage.EMBEDDER_VERSION",
            "test-bumped-v2",
        )
        result = store.ensure_index_current()
        assert result["rebuilt"] is True
        assert result["version"] == "test-bumped-v2"
    finally:
        store.close()
