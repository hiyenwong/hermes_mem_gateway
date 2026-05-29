from __future__ import annotations

import json

from .config import load_config, merge_overrides
from .maintenance_service import compact_daily, compact_user_day
from .storage import SQLiteStore


def register_cli(subparser) -> None:
    validate = subparser.add_parser("validate", help="Validate provider storage state")
    validate.set_defaults(_layered_memory_command="validate")

    rebuild = subparser.add_parser(
        "rebuild-index", help="Rebuild semantic index from SQLite"
    )
    rebuild.set_defaults(_layered_memory_command="rebuild-index")

    compact_user = subparser.add_parser(
        "compact-user", help="Run daily maintenance for one Gateway user"
    )
    compact_user.add_argument("--profile", default="", help="Profile identifier")
    compact_user.add_argument("--workspace", default="", help="Workspace identifier")
    compact_user.add_argument(
        "--date", required=True, help="Maintenance date in YYYY-MM-DD format"
    )
    compact_user.add_argument(
        "--user-email", default="", help="Stable Gateway user email"
    )
    compact_user.add_argument("--user-id", default="", help="Stable Gateway user id")
    compact_user.add_argument(
        "--user-name", default="", help="Gateway display name for provenance only"
    )
    compact_user.add_argument(
        "--force", action="store_true", help="Re-run a completed maintenance key"
    )
    compact_user.set_defaults(_layered_memory_command="compact-user")

    compact_daily_parser = subparser.add_parser(
        "compact-daily", help="Run daily maintenance for all known user principals"
    )
    compact_daily_parser.add_argument(
        "--profile", default="", help="Profile identifier"
    )
    compact_daily_parser.add_argument(
        "--workspace", default="", help="Workspace identifier"
    )
    compact_daily_parser.add_argument(
        "--date", required=True, help="Maintenance date in YYYY-MM-DD format"
    )
    compact_daily_parser.add_argument(
        "--force", action="store_true", help="Re-run completed maintenance keys"
    )
    compact_daily_parser.set_defaults(_layered_memory_command="compact-daily")


def run_cli(args, hermes_home: str) -> int:
    config = merge_overrides(
        load_config(hermes_home),
        [
            ("profile_id", getattr(args, "profile", "") or None),
            ("memory_workspace", getattr(args, "workspace", "") or None),
        ],
    )
    base = config.storage_base(hermes_home)
    store = SQLiteStore(
        base / "memory.sqlite3",
        dimensions=config.embedding_dimensions,
        index_path=base / "lancedb",
    )
    store.bootstrap()
    try:
        command = getattr(args, "_layered_memory_command", "")
        if command == "rebuild-index":
            result = {"rebuilt": store.rebuild_index()}
        elif command == "compact-user":
            result = compact_user_day(
                store=store,
                config=config,
                date=args.date,
                user_email=args.user_email,
                user_id=args.user_id,
                user_name=args.user_name,
                force=args.force,
            ).to_mapping()
        elif command == "compact-daily":
            result = compact_daily(
                store=store,
                config=config,
                date=args.date,
                force=args.force,
            )
        else:
            result = store.validate()
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    finally:
        store.close()
