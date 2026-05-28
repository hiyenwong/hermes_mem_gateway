from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from .config import ProviderConfig
from .namespace import NamespaceContext, SHARED_PRINCIPAL


SHARED_MEMORY_RE = re.compile(
    r"(?:\b(?:remember this as shared|save this to shared memory|share this memory)\b|保存为共享记忆|记到共享记忆里)",
    re.I,
)

MemoryLayer = Literal["episodic", "semantic_user", "semantic_shared"]


@dataclass(frozen=True)
class SharedIntentDecision:
    requested: bool
    source: str


@dataclass(frozen=True)
class WriteDecision:
    allowed: bool
    layer: str | None
    principal_id: str | None
    reason: str
    shared_intent: SharedIntentDecision
    shared_authorized: bool
    metadata: dict[str, object]


@dataclass(frozen=True)
class RecallScope:
    title: str
    layer: MemoryLayer
    principal_id: str
    session_id: str
    semantic: bool
    date_filter: str = ""
    exclude_session_id: str = ""


@dataclass(frozen=True)
class MaintenanceWriteDecision:
    allowed: bool
    layer: str | None
    principal_id: str | None
    reason: str
    metadata: dict[str, object]


def _normalize_sentence(text: str) -> str:
    return " ".join(text.strip().split())


def resolve_shared_intent(user_text: str, metadata_shared_intent: bool | None) -> SharedIntentDecision:
    if metadata_shared_intent is not None:
        return SharedIntentDecision(metadata_shared_intent, "metadata")
    if SHARED_MEMORY_RE.search(_normalize_sentence(user_text)):
        return SharedIntentDecision(True, "natural_language")
    return SharedIntentDecision(False, "none")


def shared_write_allowed(
    config: ProviderConfig,
    namespace: NamespaceContext,
    shared_intent: SharedIntentDecision,
) -> bool:
    if not namespace.is_gateway:
        return namespace.agent_context == "primary" and (
            shared_intent.requested or not config.shared_explicit_required
        )
    if not namespace.user_email:
        return False
    if namespace.user_email not in set(config.shared_writer_emails):
        return False
    if config.shared_explicit_required and not shared_intent.requested:
        return False
    return namespace.agent_context == "primary"


def policy_metadata(
    namespace: NamespaceContext,
    shared_intent: SharedIntentDecision,
    *,
    shared_authorized: bool,
    reason: str,
) -> dict[str, object]:
    return {
        "gateway_user": namespace.is_gateway,
        "principal_source": namespace.principal_source,
        "resolved_user_email": namespace.user_email,
        "resolved_user_id": namespace.user_id,
        "resolved_user_name": namespace.user_name,
        "shared_requested": shared_intent.requested,
        "shared_request_source": shared_intent.source,
        "shared_authorized": shared_authorized,
        "policy_reason": reason,
        "privacy_scope": "private" if namespace.is_gateway else "shared",
    }


def promotion_write_decision(
    config: ProviderConfig,
    namespace: NamespaceContext,
    *,
    content: str,
) -> WriteDecision:
    shared_intent = resolve_shared_intent(content, namespace.metadata_shared_intent)
    shared_authorized = shared_write_allowed(config, namespace, shared_intent)
    if shared_authorized:
        reason = "shared_authorized"
        return WriteDecision(
            True,
            "semantic_shared",
            SHARED_PRINCIPAL,
            reason,
            shared_intent,
            shared_authorized,
            policy_metadata(namespace, shared_intent, shared_authorized=shared_authorized, reason=reason),
        )

    if namespace.agent_context != "primary" and not config.allow_non_primary_durable_writes:
        reason = "non_primary_blocked"
        return _denied(namespace, shared_intent, shared_authorized, reason)

    if namespace.is_gateway:
        if namespace.principal_id == SHARED_PRINCIPAL:
            reason = "gateway_principal_missing"
            return _denied(namespace, shared_intent, shared_authorized, reason)
        reason = "gateway_private_user"
        return WriteDecision(
            True,
            "semantic_user",
            namespace.principal_id,
            reason,
            shared_intent,
            shared_authorized,
            policy_metadata(namespace, shared_intent, shared_authorized=shared_authorized, reason=reason),
        )

    reason = "non_gateway_shared"
    return WriteDecision(
        True,
        "semantic_shared",
        SHARED_PRINCIPAL,
        reason,
        shared_intent,
        shared_authorized,
        policy_metadata(namespace, shared_intent, shared_authorized=shared_authorized, reason=reason),
    )


def memory_write_decision(
    config: ProviderConfig,
    namespace: NamespaceContext,
    *,
    target: str,
    content: str,
) -> WriteDecision:
    shared_intent = resolve_shared_intent(content, namespace.metadata_shared_intent)
    shared_authorized = shared_write_allowed(config, namespace, shared_intent)

    if namespace.agent_context != "primary" and not config.allow_non_primary_durable_writes:
        reason = "non_primary_blocked"
        return _denied(namespace, shared_intent, shared_authorized, reason)

    if namespace.is_gateway:
        if shared_authorized:
            reason = "shared_authorized"
            return WriteDecision(
                True,
                "semantic_shared",
                SHARED_PRINCIPAL,
                reason,
                shared_intent,
                shared_authorized,
                policy_metadata(namespace, shared_intent, shared_authorized=shared_authorized, reason=reason),
            )
        if namespace.principal_id == SHARED_PRINCIPAL:
            reason = "gateway_principal_missing"
            return _denied(namespace, shared_intent, shared_authorized, reason)
        reason = "gateway_private_user"
        return WriteDecision(
            True,
            "semantic_user",
            namespace.principal_id,
            reason,
            shared_intent,
            shared_authorized,
            policy_metadata(namespace, shared_intent, shared_authorized=shared_authorized, reason=reason),
        )

    reason = "non_gateway_shared"
    return WriteDecision(
        True,
        "semantic_shared",
        SHARED_PRINCIPAL,
        reason,
        shared_intent,
        shared_authorized,
        policy_metadata(namespace, shared_intent, shared_authorized=shared_authorized, reason=reason),
    )


def maintenance_user_write_decision(
    namespace: NamespaceContext,
    *,
    target_principal_id: str,
    operation: str = "daily_compaction",
) -> MaintenanceWriteDecision:
    metadata = {
        "gateway_user": namespace.is_gateway,
        "principal_source": namespace.principal_source,
        "resolved_user_email": namespace.user_email,
        "resolved_user_id": namespace.user_id,
        "resolved_user_name": namespace.user_name,
        "maintenance": True,
        "maintenance_operation": operation,
        "privacy_scope": "private" if namespace.is_gateway else "shared",
    }
    if namespace.agent_context != "maintenance":
        reason = "not_maintenance_context"
        return MaintenanceWriteDecision(False, None, None, reason, {**metadata, "policy_reason": reason})
    if not namespace.is_gateway:
        reason = "maintenance_requires_gateway_context"
        return MaintenanceWriteDecision(False, None, None, reason, {**metadata, "policy_reason": reason})
    if namespace.principal_id == SHARED_PRINCIPAL:
        reason = "maintenance_principal_missing"
        return MaintenanceWriteDecision(False, None, None, reason, {**metadata, "policy_reason": reason})
    if target_principal_id != namespace.principal_id:
        reason = "maintenance_cross_principal_blocked"
        return MaintenanceWriteDecision(False, None, None, reason, {**metadata, "policy_reason": reason})
    reason = "maintenance_same_principal_user"
    return MaintenanceWriteDecision(
        True,
        "semantic_user",
        namespace.principal_id,
        reason,
        {**metadata, "policy_reason": reason},
    )


def recall_scopes(namespace: NamespaceContext, *, today: str = "") -> list[RecallScope]:
    today = today or datetime.now(timezone.utc).date().isoformat()
    scopes = [
        RecallScope(
            "Session episodic memory",
            "episodic",
            namespace.principal_id,
            namespace.session_id,
            False,
        )
    ]
    if namespace.is_gateway and namespace.principal_id != SHARED_PRINCIPAL:
        scopes.append(
            RecallScope(
                "Today's cross-session memory",
                "episodic",
                namespace.principal_id,
                "",
                False,
                date_filter=today,
                exclude_session_id=namespace.session_id,
            )
        )
        scopes.append(RecallScope("User semantic memory", "semantic_user", namespace.principal_id, "", True))
    scopes.append(RecallScope("Workspace shared memory", "semantic_shared", SHARED_PRINCIPAL, "", True))
    return scopes


def _denied(
    namespace: NamespaceContext,
    shared_intent: SharedIntentDecision,
    shared_authorized: bool,
    reason: str,
) -> WriteDecision:
    return WriteDecision(
        False,
        None,
        None,
        reason,
        shared_intent,
        shared_authorized,
        policy_metadata(namespace, shared_intent, shared_authorized=shared_authorized, reason=reason),
    )
