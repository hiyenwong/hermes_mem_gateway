from __future__ import annotations

from .config import ProviderConfig
from .namespace import NamespaceContext
from .policy import recall_scopes
from .prompt_format import format_memory_block, gateway_prompt_context
from .storage import SQLiteStore


def assemble_recall(
    query: str,
    *,
    config: ProviderConfig,
    namespace: NamespaceContext,
    store: SQLiteStore,
) -> str:
    blocks: list[str] = []
    gateway_context = gateway_prompt_context(config, namespace)
    if gateway_context:
        blocks.append(gateway_context)

    for scope in recall_scopes(
        namespace, platform_scoped=config.recall_platform_scoped
    ):
        if scope.semantic:
            hits = store.search_semantic(
                query,
                profile_id=namespace.profile_id,
                workspace_id=namespace.workspace_id,
                principal_id=scope.principal_id,
                session_id=scope.session_id,
                layer=scope.layer,
                limit=config.recall_limit_per_layer,
                platform=scope.platform,
            )
            if hits:
                blocks.append(
                    format_memory_block(scope.title, [hit.record for hit in hits])
                )
                for hit in hits:
                    store.reinforce(hit.record["id"])
            continue

        records = store.search_exact(
            profile_id=namespace.profile_id,
            workspace_id=namespace.workspace_id,
            principal_id=scope.principal_id,
            session_id=scope.session_id,
            layer=scope.layer,
            limit=config.recall_limit_per_layer,
            date=scope.date_filter,
            exclude_session_id=scope.exclude_session_id,
            platform=scope.platform,
        )
        if records:
            blocks.append(format_memory_block(scope.title, records))

    return "\n\n".join(blocks)
