from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import ProviderConfig


SHARED_PRINCIPAL = "__shared__"


@dataclass
class RuntimeContext:
    session_id: str
    platform: str = "cli"
    agent_context: str = "primary"
    agent_identity: str = "default"
    agent_workspace: str = ""
    parent_session_id: str = ""
    user_id: str = ""


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

    @property
    def can_write_durable(self) -> bool:
        return self.durable_user_allowed or self.durable_shared_allowed


def resolve_namespace(config: ProviderConfig, runtime: RuntimeContext) -> NamespaceContext:
    workspace_id = runtime.agent_workspace or config.memory_workspace
    platform = runtime.platform or "cli"
    agent_context = runtime.agent_context or "primary"
    is_gateway = platform in set(config.gateway_platforms)
    is_primary = agent_context == "primary"
    principal_id = SHARED_PRINCIPAL
    durable_user_allowed = False
    durable_shared_allowed = False

    if is_gateway:
        if runtime.user_id:
            principal_id = runtime.user_id
            durable_user_allowed = is_primary
        durable_shared_allowed = False
    else:
        principal_id = SHARED_PRINCIPAL
        durable_shared_allowed = is_primary

    if config.allow_non_primary_durable_writes and not is_primary:
        durable_shared_allowed = True
        if runtime.user_id:
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
    )


def runtime_from_kwargs(session_id: str, **kwargs: Any) -> RuntimeContext:
    return RuntimeContext(
        session_id=session_id,
        platform=str(kwargs.get("platform", "cli") or "cli"),
        agent_context=str(kwargs.get("agent_context", "primary") or "primary"),
        agent_identity=str(kwargs.get("agent_identity", "default") or "default"),
        agent_workspace=str(kwargs.get("agent_workspace", "") or ""),
        parent_session_id=str(kwargs.get("parent_session_id", "") or ""),
        user_id=str(kwargs.get("user_id", "") or ""),
    )
