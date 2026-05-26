from __future__ import annotations

import json
from pathlib import Path

from .config import load_config
from .storage import SQLiteStore


def register_cli(subparser) -> None:
    validate = subparser.add_parser("validate", help="Validate provider storage state")
    validate.set_defaults(_layered_memory_command="validate")

    rebuild = subparser.add_parser("rebuild-index", help="Rebuild semantic index from SQLite")
    rebuild.set_defaults(_layered_memory_command="rebuild-index")


def run_cli(args, hermes_home: str) -> int:
    config = load_config(hermes_home)
    base = config.storage_base(hermes_home)
    store = SQLiteStore(base / "memory.sqlite3", dimensions=config.embedding_dimensions, index_path=base / "lancedb")
    store.bootstrap()
    try:
        command = getattr(args, "_layered_memory_command", "")
        if command == "rebuild-index":
            result = {"rebuilt": store.rebuild_index()}
        else:
            result = store.validate()
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    finally:
        store.close()
