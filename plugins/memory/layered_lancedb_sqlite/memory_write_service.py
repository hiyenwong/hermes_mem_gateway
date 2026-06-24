from __future__ import annotations

from typing import Any

from .config import ProviderConfig
from .governance import fingerprint_text
from .namespace import NamespaceContext
from .policy import memory_write_decision
from .storage import SQLiteStore


def mirror_memory(
    *,
    store: SQLiteStore,
    config: ProviderConfig,
    namespace: NamespaceContext,
    target: str,
    content: str,
    source: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    decision = memory_write_decision(config, namespace, target=target, content=content)
    if not decision.allowed or decision.layer is None or decision.principal_id is None:
        return
    memory_id = store.insert_memory(
        profile_id=namespace.profile_id,
        workspace_id=namespace.workspace_id,
        principal_id=decision.principal_id,
        session_id=namespace.session_id,
        layer=decision.layer,
        kind="builtin_memory",
        content=content.strip(),
        fingerprint=fingerprint_text(content),
        source=source,
        importance=0.95,
        platform=namespace.platform,
        metadata={**(metadata or {}), **decision.metadata},
    )
    store.add_provenance(
        memory_id,
        source_type="builtin_memory",
        source_ref=source,
        platform=namespace.platform,
        agent_context=namespace.agent_context,
        session_id=namespace.session_id,
        metadata={**(metadata or {}), **decision.metadata},
    )
