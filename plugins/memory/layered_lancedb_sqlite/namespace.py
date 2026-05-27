from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import ProviderConfig


SHARED_PRINCIPAL = "__shared__"
OPENWEBUI_HEADER_MAP = {
    "user_email": "x-openwebui-user-email",
    "user_id": "x-openwebui-user-id",
    "user_name": "x-openwebui-user-name",
}


@dataclass
class RuntimeContext:
    session_id: str
    platform: str = "cli"
    agent_context: str = "primary"
    agent_identity: str = "default"
    agent_workspace: str = ""
    parent_session_id: str = ""
    user_id: str = ""
    user_email: str = ""
    user_name: str = ""
    principal_source: str = ""
    request_metadata: dict[str, Any] | None = None
    metadata_shared_intent: bool | None = None


@dataclass
class NamespaceContext:
    profile_id: str
    workspace_id: str
    principal_id: str
    session_id: str
    platform: str
    agent_context: str
    is_gateway: bool
    durable_user_allowed: bool
    durable_shared_allowed: bool
    user_id: str
    user_email: str
    user_name: str
    principal_source: str
    request_metadata: dict[str, Any]
    metadata_shared_intent: bool | None

    @property
    def can_write_durable(self) -> bool:
        return self.durable_user_allowed or self.durable_shared_allowed


def _canonicalize_headers(headers: Any) -> dict[str, str]:
    if not isinstance(headers, dict):
        return {}
    return {str(key).strip().lower(): str(value).strip() for key, value in headers.items() if value is not None}


def _metadata_from_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    for key in ("request_metadata", "metadata", "turn_metadata"):
        value = kwargs.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _metadata_shared_intent(metadata: dict[str, Any]) -> bool | None:
    direct_keys = ("shared_memory", "shared", "memory_shared")
    for key in direct_keys:
        if key in metadata:
            return bool(metadata[key])
    memory_meta = metadata.get("memory")
    if isinstance(memory_meta, dict) and "shared" in memory_meta:
        return bool(memory_meta["shared"])
    return None


def _identity_from_kwargs(kwargs: dict[str, Any]) -> tuple[str, str, str]:
    headers = _canonicalize_headers(
        kwargs.get("headers")
        or kwargs.get("request_headers")
        or kwargs.get("openwebui_headers")
        or {}
    )
    user_email = str(
        kwargs.get("user_email")
        or headers.get(OPENWEBUI_HEADER_MAP["user_email"], "")
        or ""
    ).strip()
    user_id = str(
        kwargs.get("user_id")
        or headers.get(OPENWEBUI_HEADER_MAP["user_id"], "")
        or ""
    ).strip()
    user_name = str(
        kwargs.get("user_name")
        or headers.get(OPENWEBUI_HEADER_MAP["user_name"], "")
        or ""
    ).strip()
    return user_email, user_id, user_name


def resolve_namespace(config: ProviderConfig, runtime: RuntimeContext) -> NamespaceContext:
    workspace_id = runtime.agent_workspace or config.memory_workspace
    platform = runtime.platform or "cli"
    agent_context = runtime.agent_context or "primary"
    is_gateway = platform in set(config.gateway_platforms)
    is_primary = agent_context == "primary"
    principal_id = SHARED_PRINCIPAL
    principal_source = ""
    durable_user_allowed = False
    durable_shared_allowed = False

    if is_gateway:
        # dslm_agent policy: Gateway users MUST NOT write durable user memory.
        # durable_user_allowed is always False regardless of user identity.
        # This prevents per-user memory contamination in shared accounts.
        durable_user_allowed = False
        if runtime.user_email:
            principal_id = runtime.user_email
            principal_source = "user_email"
        elif runtime.user_id:
            principal_id = runtime.user_id
            principal_source = "user_id"
        allowlisted = runtime.user_email in set(config.shared_writer_emails)
        durable_shared_allowed = is_primary and allowlisted
    else:
        principal_id = SHARED_PRINCIPAL
        durable_shared_allowed = is_primary

    if config.allow_non_primary_durable_writes and not is_primary:
        durable_shared_allowed = True
        # dslm_agent policy: Even if allow_non_primary_durable_writes is True,
        # Gateway users MUST NOT get durable_user_allowed. Only non-gateway
        # (CLI/cron) non-primary contexts may write user memory.
        if not is_gateway:
            if runtime.user_email:
                durable_user_allowed = True
            elif runtime.user_id:
                durable_user_allowed = True

    return NamespaceContext(
        profile_id=config.profile_id,
        workspace_id=workspace_id,
        principal_id=principal_id,
        session_id=runtime.session_id,
        platform=platform,
        agent_context=agent_context,
        is_gateway=is_gateway,
        durable_user_allowed=durable_user_allowed,
        durable_shared_allowed=durable_shared_allowed,
        user_id=runtime.user_id,
        user_email=runtime.user_email,
        user_name=runtime.user_name,
        principal_source=principal_source or runtime.principal_source,
        request_metadata=runtime.request_metadata or {},
        metadata_shared_intent=runtime.metadata_shared_intent,
    )


def runtime_from_kwargs(session_id: str, **kwargs: Any) -> RuntimeContext:
    metadata = _metadata_from_kwargs(kwargs)
    user_email, user_id, user_name = _identity_from_kwargs(kwargs)
    return RuntimeContext(
        session_id=session_id,
        platform=str(kwargs.get("platform", "cli") or "cli"),
        agent_context=str(kwargs.get("agent_context", "primary") or "primary"),
        agent_identity=str(kwargs.get("agent_identity", "default") or "default"),
        agent_workspace=str(kwargs.get("agent_workspace", "") or ""),
        parent_session_id=str(kwargs.get("parent_session_id", "") or ""),
        user_id=user_id,
        user_email=user_email,
        user_name=user_name,
        principal_source="user_email" if user_email else ("user_id" if user_id else ""),
        request_metadata=metadata,
        metadata_shared_intent=_metadata_shared_intent(metadata),
    )
