"""Tests for identity_sidecar read/write and namespace sidecar fallback."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from plugins.memory.layered_lancedb_sqlite.identity_sidecar import (
    read_identity,
    write_identity,
)
from plugins.memory.layered_lancedb_sqlite.namespace import runtime_from_kwargs


# ---------------------------------------------------------------------------
# identity_sidecar unit tests
# ---------------------------------------------------------------------------


def test_write_then_read_roundtrip(tmp_path: Path) -> None:
    sidecar_dir = str(tmp_path)
    write_identity(
        "sess-1",
        email="user@example.com",
        name="Alice",
        user_id="u1",
        sidecar_dir=sidecar_dir,
    )
    result = read_identity("sess-1", sidecar_dir=sidecar_dir)
    assert result is not None
    assert result["email"] == "user@example.com"
    assert result["name"] == "Alice"
    assert result["user_id"] == "u1"


def test_read_missing_returns_none(tmp_path: Path) -> None:
    assert read_identity("no-such-session", sidecar_dir=str(tmp_path)) is None


def test_read_expired_returns_none(tmp_path: Path) -> None:
    sidecar_dir = str(tmp_path)
    write_identity("sess-old", email="old@example.com", sidecar_dir=sidecar_dir)
    # Backdate the file's ts by 25 hours
    path = tmp_path / "sess-old.json"
    data = json.loads(path.read_text())
    data["ts"] = int(time.time()) - 25 * 3600
    path.write_text(json.dumps(data))
    assert read_identity("sess-old", sidecar_dir=sidecar_dir, ttl_hours=24) is None


def test_read_within_ttl_returns_data(tmp_path: Path) -> None:
    sidecar_dir = str(tmp_path)
    write_identity("sess-fresh", email="fresh@example.com", sidecar_dir=sidecar_dir)
    result = read_identity("sess-fresh", sidecar_dir=sidecar_dir, ttl_hours=24)
    assert result is not None
    assert result["email"] == "fresh@example.com"


def test_write_empty_session_id_is_noop(tmp_path: Path) -> None:
    write_identity("", email="a@b.com", sidecar_dir=str(tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_read_corrupted_file_returns_none(tmp_path: Path) -> None:
    sidecar_dir = str(tmp_path)
    (tmp_path / "bad.json").write_text("not-json{{{")
    assert read_identity("bad", sidecar_dir=sidecar_dir) is None


# ---------------------------------------------------------------------------
# namespace sidecar fallback integration tests
# ---------------------------------------------------------------------------


def test_runtime_uses_sidecar_when_headers_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sidecar_dir = str(tmp_path)
    monkeypatch.setenv("LAYERED_MEMORY_IDENTITY_SIDECAR_DIR", sidecar_dir)
    write_identity(
        "chat-42", email="robin@example.com", name="Robin", sidecar_dir=sidecar_dir
    )

    runtime = runtime_from_kwargs("chat-42", platform="gateway")

    assert runtime.user_email == "robin@example.com"
    assert runtime.user_name == "Robin"


def test_runtime_header_wins_over_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sidecar_dir = str(tmp_path)
    monkeypatch.setenv("LAYERED_MEMORY_IDENTITY_SIDECAR_DIR", sidecar_dir)
    write_identity("chat-43", email="sidecar@example.com", sidecar_dir=sidecar_dir)

    runtime = runtime_from_kwargs(
        "chat-43",
        platform="gateway",
        headers={"x-openwebui-user-email": "header@example.com"},
    )

    assert runtime.user_email == "header@example.com"


def test_runtime_sidecar_not_used_on_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sidecar_dir = str(tmp_path)
    monkeypatch.setenv("LAYERED_MEMORY_IDENTITY_SIDECAR_DIR", sidecar_dir)
    write_identity("chat-44", email="robin@example.com", sidecar_dir=sidecar_dir)

    runtime = runtime_from_kwargs("chat-44", platform="cli")

    assert runtime.user_email == ""


def test_runtime_sidecar_not_used_when_already_resolved_from_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sidecar_dir = str(tmp_path)
    monkeypatch.setenv("LAYERED_MEMORY_IDENTITY_SIDECAR_DIR", sidecar_dir)
    write_identity("chat-45", email="sidecar@example.com", sidecar_dir=sidecar_dir)

    messages = [
        {
            "role": "system",
            "content": "# Current User\nEmail: body@example.com\nName: Body User",
        }
    ]
    runtime = runtime_from_kwargs("chat-45", platform="gateway", messages=messages)

    assert runtime.user_email == "body@example.com"
