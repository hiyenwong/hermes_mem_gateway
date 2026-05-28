from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from .config import ProviderConfig
from .governance import fingerprint_text
from .namespace import NamespaceContext, resolve_namespace, runtime_from_kwargs
from .policy import maintenance_user_write_decision
from .storage import SQLiteStore


OPERATION_DAILY_COMPACTION = "daily_compaction"


@dataclass
class MaintenanceResult:
    principal_id: str
    date: str
    state_key: str
    status: str
    processed_count: int = 0
    archived_count: int = 0
    output_memory_id: str = ""
    skipped: bool = False
    error: str = ""
    truncated_to_limit: int = 0

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


def maintenance_state_key(
    *,
    operation: str,
    profile_id: str,
    workspace_id: str,
    principal_id: str,
    date: str,
) -> str:
    return f"{operation}:{profile_id}:{workspace_id}:{principal_id}:{date}"


def maintenance_namespace(
    config: ProviderConfig,
    *,
    date: str,
    user_email: str = "",
    user_id: str = "",
    user_name: str = "",
    user_id_alt: str = "",
) -> NamespaceContext:
    if not (user_email or user_id or user_id_alt):
        raise ValueError("maintenance requires stable user_email, user_id, or user_id_alt")
    principal_hint = user_email or user_id or user_id_alt
    session_id = f"maintenance:{date}:{principal_hint}"
    runtime = runtime_from_kwargs(
        session_id,
        platform="gateway",
        agent_context="maintenance",
        agent_identity=config.profile_id,
        agent_workspace=config.memory_workspace,
        user_email=user_email,
        user_id=user_id,
        user_name=user_name,
        user_id_alt=user_id_alt,
        request_metadata={
            "maintenance": True,
            "maintenance_kind": OPERATION_DAILY_COMPACTION,
        },
    )
    return resolve_namespace(config, runtime)


def compact_user_day(
    *,
    store: SQLiteStore,
    config: ProviderConfig,
    date: str,
    user_email: str = "",
    user_id: str = "",
    user_name: str = "",
    user_id_alt: str = "",
    force: bool = False,
) -> MaintenanceResult:
    _validate_date(date)
    namespace = maintenance_namespace(
        config,
        date=date,
        user_email=user_email,
        user_id=user_id,
        user_name=user_name,
        user_id_alt=user_id_alt,
    )
    key = maintenance_state_key(
        operation=OPERATION_DAILY_COMPACTION,
        profile_id=namespace.profile_id,
        workspace_id=namespace.workspace_id,
        principal_id=namespace.principal_id,
        date=date,
    )
    existing_state = store.get_maintenance_state(key)
    if existing_state and existing_state.get("status") == "completed" and not force:
        return MaintenanceResult(
            principal_id=namespace.principal_id,
            date=date,
            state_key=key,
            status="completed",
            processed_count=int(existing_state.get("processed_count", 0)),
            archived_count=int(existing_state.get("archived_count", 0)),
            output_memory_id=str(existing_state.get("output_memory_id", "")),
            skipped=True,
            truncated_to_limit=int(existing_state.get("truncated_to_limit", 0)),
        )

    store.set_maintenance_state(
        key,
        {
            "status": "started",
            "operation": OPERATION_DAILY_COMPACTION,
            "profile_id": namespace.profile_id,
            "workspace_id": namespace.workspace_id,
            "principal_id": namespace.principal_id,
            "date": date,
        },
    )
    try:
        result = _compact_started_user_day(store=store, config=config, namespace=namespace, date=date, key=key)
    except Exception as exc:
        store.set_maintenance_state(
            key,
            {
                "status": "failed",
                "operation": OPERATION_DAILY_COMPACTION,
                "profile_id": namespace.profile_id,
                "workspace_id": namespace.workspace_id,
                "principal_id": namespace.principal_id,
                "date": date,
                "error": str(exc),
            },
        )
        raise
    store.set_maintenance_state(
        key,
        {
            "status": result.status,
            "operation": OPERATION_DAILY_COMPACTION,
            "profile_id": namespace.profile_id,
            "workspace_id": namespace.workspace_id,
            "principal_id": namespace.principal_id,
            "date": date,
            "processed_count": result.processed_count,
            "archived_count": result.archived_count,
            "output_memory_id": result.output_memory_id,
            "truncated_to_limit": result.truncated_to_limit,
        },
    )
    return result


def compact_daily(
    *,
    store: SQLiteStore,
    config: ProviderConfig,
    date: str,
    force: bool = False,
) -> dict[str, Any]:
    principals = store.list_user_principals(profile_id=config.profile_id, workspace_id=config.memory_workspace)
    results: list[dict[str, Any]] = []
    completed = 0
    failed = 0
    skipped = 0
    for principal in principals:
        principal_id = principal["principal_id"]
        user_email, user_id, user_id_alt = _split_principal(principal_id, principal["principal_source"])
        try:
            result = compact_user_day(
                store=store,
                config=config,
                date=date,
                user_email=user_email,
                user_id=user_id,
                user_id_alt=user_id_alt,
                force=force,
            )
        except Exception as exc:
            failed += 1
            results.append(
                MaintenanceResult(
                    principal_id=principal_id,
                    date=date,
                    state_key=maintenance_state_key(
                        operation=OPERATION_DAILY_COMPACTION,
                        profile_id=config.profile_id,
                        workspace_id=config.memory_workspace,
                        principal_id=principal_id,
                        date=date,
                    ),
                    status="failed",
                    error=str(exc),
                ).to_mapping()
            )
            continue
        if result.skipped:
            skipped += 1
        elif result.status == "completed":
            completed += 1
        results.append(result.to_mapping())
    return {
        "status": "completed" if failed == 0 else "failed",
        "date": date,
        "processed_principals": len(principals),
        "completed": completed,
        "failed": failed,
        "skipped": skipped,
        "results": results,
    }


def _split_principal(principal_id: str, principal_source: str) -> tuple[str, str, str]:
    if principal_source == "user_email":
        return principal_id, "", ""
    if principal_source == "user_id":
        return "", principal_id, ""
    if principal_source == "user_id_alt":
        return "", "", principal_id
    if "@" in principal_id:
        return principal_id, "", ""
    return "", principal_id, ""


def _compact_started_user_day(
    *,
    store: SQLiteStore,
    config: ProviderConfig,
    namespace: NamespaceContext,
    date: str,
    key: str,
) -> MaintenanceResult:
    limit = config.maintenance_max_records_per_day
    fetch_limit = limit + 1 if limit and limit > 0 else None
    records = store.fetch_user_records_for_date(
        profile_id=namespace.profile_id,
        workspace_id=namespace.workspace_id,
        principal_id=namespace.principal_id,
        date=date,
        layer="semantic_user",
        limit=fetch_limit,
    )
    truncated_to_limit = 0
    if fetch_limit and len(records) > limit:
        truncated_to_limit = limit
        records = records[:limit]
    archived_ids = _archive_duplicate_fingerprints(store, records, namespace=namespace, date=date, state_key=key)
    active_records = [record for record in records if record["status"] == "active" and record["id"] not in archived_ids]
    decision = maintenance_user_write_decision(
        namespace,
        target_principal_id=namespace.principal_id,
        operation=OPERATION_DAILY_COMPACTION,
    )
    if not decision.allowed or decision.layer is None or decision.principal_id is None:
        raise RuntimeError(decision.reason)
    output_memory_id = ""
    if active_records:
        content = _compact_content(date, active_records)
        output_memory_id = store.insert_memory(
            profile_id=namespace.profile_id,
            workspace_id=namespace.workspace_id,
            principal_id=decision.principal_id,
            session_id=namespace.session_id,
            layer=decision.layer,
            kind="daily_compaction_summary",
            content=content,
            fingerprint=fingerprint_text(f"{key}:{content}"),
            source=OPERATION_DAILY_COMPACTION,
            importance=0.7,
            metadata={
                **decision.metadata,
                "maintenance_date": date,
                "maintenance_state_key": key,
                "processed_count": len(active_records),
                "archived_count": len(archived_ids),
                "truncated_to_limit": truncated_to_limit,
            },
        )
        store.add_provenance(
            output_memory_id,
            source_type=OPERATION_DAILY_COMPACTION,
            source_ref=key,
            platform=namespace.platform,
            agent_context=namespace.agent_context,
            session_id=namespace.session_id,
            metadata={
                **decision.metadata,
                "maintenance_date": date,
                "maintenance_state_key": key,
                "truncated_to_limit": truncated_to_limit,
            },
        )
    return MaintenanceResult(
        principal_id=namespace.principal_id,
        date=date,
        state_key=key,
        status="completed",
        processed_count=len(active_records),
        archived_count=len(archived_ids),
        output_memory_id=output_memory_id,
        truncated_to_limit=truncated_to_limit,
    )


def _archive_duplicate_fingerprints(
    store: SQLiteStore,
    records: list[dict[str, Any]],
    *,
    namespace: NamespaceContext,
    date: str,
    state_key: str,
) -> set[str]:
    by_fingerprint: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_fingerprint.setdefault(str(record["fingerprint"]), []).append(record)
    archived: set[str] = set()
    for duplicates in by_fingerprint.values():
        if len(duplicates) <= 1:
            continue
        for record in duplicates[1:]:
            store.archive(
                str(record["id"]),
                {
                    **record.get("metadata", {}),
                    "maintenance": True,
                    "maintenance_operation": OPERATION_DAILY_COMPACTION,
                    "maintenance_reason": "duplicate_fingerprint",
                    "maintenance_date": date,
                    "maintenance_state_key": state_key,
                    "maintenance_principal": namespace.principal_id,
                },
            )
            archived.add(str(record["id"]))
    return archived


def _compact_content(date: str, records: list[dict[str, Any]]) -> str:
    lines = [f"Daily memory maintenance summary for {date}:"]
    for idx, record in enumerate(records, start=1):
        lines.append(f"{idx}. {record['content']}")
    return "\n".join(lines)


def _validate_date(date: str) -> None:
    datetime.strptime(date, "%Y-%m-%d")
