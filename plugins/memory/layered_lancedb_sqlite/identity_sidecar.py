from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


_ENV_DIR = "LAYERED_MEMORY_IDENTITY_SIDECAR_DIR"
_ENV_TTL = "LAYERED_MEMORY_IDENTITY_SIDECAR_TTL_HOURS"
_DEFAULT_TTL_HOURS = 24


def _sidecar_dir(override: str = "") -> Path:
    raw = override or os.environ.get(_ENV_DIR, "")
    return Path(raw) if raw else Path.home() / ".cache" / "hermes_identity"


def _sidecar_path(session_id: str, sidecar_dir: str = "") -> Path:
    return _sidecar_dir(sidecar_dir) / f"{session_id}.json"


def write_identity(
    session_id: str,
    *,
    email: str = "",
    name: str = "",
    user_id: str = "",
    sidecar_dir: str = "",
) -> None:
    if not session_id:
        return
    path = _sidecar_path(session_id, sidecar_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"email": email, "name": name, "user_id": user_id, "ts": int(time.time())}
        )
    )


def read_identity(
    session_id: str,
    *,
    sidecar_dir: str = "",
    ttl_hours: int = 0,
) -> dict[str, Any] | None:
    if not session_id:
        return None
    if ttl_hours <= 0:
        ttl_hours = int(os.environ.get(_ENV_TTL, _DEFAULT_TTL_HOURS))
    path = _sidecar_path(session_id, sidecar_dir)
    if not path.exists():
        return None
    try:
        data: dict[str, Any] = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if (time.time() - float(data.get("ts", 0))) > ttl_hours * 3600:
        return None
    return data
