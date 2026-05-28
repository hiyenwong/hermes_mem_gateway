from __future__ import annotations

from .config import ProviderConfig
from .governance import classify_turn, find_superseded, rank_record
from .namespace import NamespaceContext
from .policy import promotion_write_decision
from .storage import SQLiteStore


def consolidate_turn(
    *,
    store: SQLiteStore,
    config: ProviderConfig,
    namespace: NamespaceContext,
    user: str,
    assistant: str,
) -> None:
    for candidate in classify_turn(user, assistant):
        if candidate.confidence < config.promotion_min_score:
            continue
        decision = promotion_write_decision(config, namespace, content=user)
        if not decision.allowed or decision.layer is None or decision.principal_id is None:
            continue
        existing = store.fetch_existing_durable(
            profile_id=namespace.profile_id,
            workspace_id=namespace.workspace_id,
            principal_id=decision.principal_id,
            layer=decision.layer,
        )
        exact = next((row for row in existing if row["fingerprint"] == candidate.fingerprint), None)
        if exact:
            store.reinforce(exact["id"])
            continue
        supersedes_id = find_superseded(existing, candidate)
        memory_id = store.insert_memory(
            profile_id=namespace.profile_id,
            workspace_id=namespace.workspace_id,
            principal_id=decision.principal_id,
            session_id=namespace.session_id,
            layer=decision.layer,
            kind=candidate.kind,
            content=candidate.content,
            fingerprint=candidate.fingerprint,
            source="promotion",
            importance=candidate.confidence,
            metadata={
                "platform": namespace.platform,
                "agent_context": namespace.agent_context,
                **decision.metadata,
            },
            supersedes_id=supersedes_id,
        )
        store.add_provenance(
            memory_id,
            source_type="promotion",
            source_ref=namespace.session_id,
            platform=namespace.platform,
            agent_context=namespace.agent_context,
            session_id=namespace.session_id,
            metadata=decision.metadata,
        )
        if candidate.confidence < 0.9 and decision.layer.startswith("semantic"):
            score = rank_record(candidate.confidence, reinforcement_count=0, access_count=0, archived=False)
            if score < config.promotion_min_score:
                store.archive(memory_id)
