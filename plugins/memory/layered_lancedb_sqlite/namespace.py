from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .config import ProviderConfig
from .identity_sidecar import read_identity as _read_sidecar


SHARED_PRINCIPAL = "__shared__"
DEFAULT_PLATFORM = "cli"
# Header keys MUST be all lowercase: incoming headers are canonicalized via
# _canonicalize_headers() which lowercases every key, so matching is
# case-insensitive regardless of how the gateway capitalizes them
# (e.g. "X-Hermes-User-Id" -> "x-hermes-user-id").
HERMES_HEADER_MAP = {
    "user_email": "x-hermes-user-email",
    "user_id": "x-hermes-user-id",
    "user_name": "x-hermes-user-name",
    "platform": "x-hermes-platform",
}
OPENWEBUI_HEADER_MAP = {
    "user_email": "x-openwebui-user-email",
    "user_id": "x-openwebui-user-id",
    "user_name": "x-openwebui-user-name",
}

_CURRENT_USER_BLOCK_RE = re.compile(r"#\s*Current User\b", re.IGNORECASE)
_USER_INFO_EMAIL_RE = re.compile(r"^Email:\s*(\S+@\S+)\s*$", re.MULTILINE)
_USER_INFO_NAME_RE = re.compile(r"^Name:\s*(.+?)\s*$", re.MULTILINE)
_AUTHENTICATED_USER_RE = re.compile(
    r"authenticated user:\s*\*\*([^*]+)\*\*", re.IGNORECASE
)


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
    user_id_alt: str = ""
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
    user_id_alt: str
    principal_source: str
    request_metadata: dict[str, Any]
    metadata_shared_intent: bool | None

    @property
    def can_write_durable(self) -> bool:
        return self.durable_user_allowed or self.durable_shared_allowed


def _canonicalize_headers(headers: Any) -> dict[str, str]:
    if not isinstance(headers, dict):
        return {}
    return {
        str(key).strip().lower(): str(value).strip()
        for key, value in headers.items()
        if value is not None
    }


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


def _headers_from_kwargs(kwargs: dict[str, Any]) -> dict[str, str]:
    return _canonicalize_headers(
        kwargs.get("headers")
        or kwargs.get("request_headers")
        or kwargs.get("hermes_headers")
        or kwargs.get("openwebui_headers")
        or {}
    )


def _header_value(headers: dict[str, str], field: str) -> str:
    """Read an identity field from canonicalized headers, Hermes first.

    Keys in both maps are lowercase; headers are already lowercased by
    _canonicalize_headers, so matching is case-insensitive regardless of the
    capitalization the gateway sends (e.g. ``X-Hermes-User-Id``).
    """
    hermes_key = HERMES_HEADER_MAP.get(field)
    if hermes_key:
        value = headers.get(hermes_key, "")
        if value:
            return value
    openwebui_key = OPENWEBUI_HEADER_MAP.get(field)
    if openwebui_key:
        return headers.get(openwebui_key, "")
    return ""


def _platform_from_kwargs(kwargs: dict[str, Any]) -> str:
    explicit = str(kwargs.get("platform", "") or "").strip()
    if explicit:
        return explicit
    headers = _headers_from_kwargs(kwargs)
    header_platform = headers.get(HERMES_HEADER_MAP["platform"], "").strip()
    if header_platform:
        return header_platform
    return DEFAULT_PLATFORM


def _identity_from_kwargs(kwargs: dict[str, Any]) -> tuple[str, str, str, str]:
    headers = _headers_from_kwargs(kwargs)
    user_email = str(
        kwargs.get("user_email") or _header_value(headers, "user_email") or ""
    ).strip()
    user_id = str(
        kwargs.get("user_id") or _header_value(headers, "user_id") or ""
    ).strip()
    user_name = str(
        kwargs.get("user_name") or _header_value(headers, "user_name") or ""
    ).strip()
    user_id_alt = str(kwargs.get("user_id_alt") or "").strip()
    if not (user_email or user_id) and _is_gatewayish_kwargs(kwargs):
        body_email, body_id, body_name = _identity_from_messages(
            _messages_from_kwargs(kwargs)
        )
        user_email = user_email or body_email
        user_id = user_id or body_id
        user_name = user_name or body_name
    return user_email, user_id, user_name, user_id_alt


def _is_gatewayish_kwargs(kwargs: dict[str, Any]) -> bool:
    platform = _platform_from_kwargs(kwargs).lower()
    return bool(platform) and platform != DEFAULT_PLATFORM


def _messages_from_kwargs(kwargs: dict[str, Any]) -> list[Any]:
    for key in ("messages", "request_messages", "body_messages"):
        value = kwargs.get(key)
        if isinstance(value, list):
            return value
    body = kwargs.get("body") or kwargs.get("request_body")
    if isinstance(body, dict):
        messages = body.get("messages")
        if isinstance(messages, list):
            return messages
    return []


def _system_message_text(message: Any) -> str:
    if not isinstance(message, dict) or message.get("role") != "system":
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return ""


def _identity_from_messages(messages: Any) -> tuple[str, str, str]:
    if not isinstance(messages, list):
        return "", "", ""
    user_email = ""
    user_name = ""
    user_id = ""
    for message in messages:
        text = _system_message_text(message)
        if not text:
            continue
        if _CURRENT_USER_BLOCK_RE.search(text):
            if not user_email:
                match = _USER_INFO_EMAIL_RE.search(text)
                if match:
                    user_email = match.group(1).strip()
            if not user_name:
                match = _USER_INFO_NAME_RE.search(text)
                if match:
                    user_name = match.group(1).strip()
        if not user_email:
            match = _AUTHENTICATED_USER_RE.search(text)
            if match:
                candidate = match.group(1).strip()
                if "@" in candidate:
                    user_email = candidate
                elif not user_name:
                    user_name = candidate
    return user_email, user_id, user_name


def resolve_namespace(
    config: ProviderConfig, runtime: RuntimeContext
) -> NamespaceContext:
    workspace_id = runtime.agent_workspace or config.memory_workspace
    platform = runtime.platform or DEFAULT_PLATFORM
    agent_context = runtime.agent_context or "primary"
    is_gateway = _is_gateway(config, runtime)
    is_primary = agent_context == "primary"
    principal_id = SHARED_PRINCIPAL
    principal_source = ""
    durable_user_allowed = False
    durable_shared_allowed = False

    if is_gateway:
        principal_id, principal_source = _gateway_principal(config, runtime)
        if principal_source:
            durable_user_allowed = is_primary
        allowlisted = runtime.user_email in set(config.shared_writer_emails)
        durable_shared_allowed = is_primary and allowlisted
    else:
        principal_id = SHARED_PRINCIPAL
        durable_shared_allowed = is_primary

    if config.allow_non_primary_durable_writes and not is_primary:
        durable_shared_allowed = True
        if principal_source:
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
        user_id_alt=runtime.user_id_alt,
        principal_source=principal_source or runtime.principal_source,
        request_metadata=runtime.request_metadata or {},
        metadata_shared_intent=runtime.metadata_shared_intent,
    )


def _is_gateway(config: ProviderConfig, runtime: RuntimeContext) -> bool:
    """A request is a gateway request if it carries any identity signal.

    Since X-Hermes-Platform is an arbitrary, caller-defined value, the platform
    allowlist alone cannot identify gateway traffic. Any resolved identity
    (email/id/id_alt) or a non-CLI platform marks the request as a gateway user
    so its memory is isolated per principal. The platform allowlist is kept as
    an additional signal for backward compatibility.
    """
    if runtime.user_email or runtime.user_id or runtime.user_id_alt:
        return True
    platform = (runtime.platform or "").strip()
    if platform and platform.lower() != DEFAULT_PLATFORM:
        return True
    return platform in set(config.gateway_platforms)


def _gateway_principal(
    config: ProviderConfig, runtime: RuntimeContext
) -> tuple[str, str]:
    if runtime.user_email:
        return runtime.user_email, "user_email"
    if config.prefer_user_id_alt and runtime.user_id_alt:
        return runtime.user_id_alt, "user_id_alt"
    if runtime.user_id:
        return runtime.user_id, "user_id"
    if runtime.user_id_alt:
        return runtime.user_id_alt, "user_id_alt"
    return SHARED_PRINCIPAL, ""


def runtime_from_kwargs(session_id: str, **kwargs: Any) -> RuntimeContext:
    metadata = _metadata_from_kwargs(kwargs)
    user_email, user_id, user_name, user_id_alt = _identity_from_kwargs(kwargs)
    if not (user_email or user_id) and _is_gatewayish_kwargs(kwargs):
        sidecar = _read_sidecar(session_id)
        if sidecar:
            user_email = user_email or str(sidecar.get("email") or "")
            user_id = user_id or str(sidecar.get("user_id") or "")
            user_name = user_name or str(sidecar.get("name") or "")
    if user_email:
        principal_hint = "user_email"
    elif user_id:
        principal_hint = "user_id"
    elif user_id_alt:
        principal_hint = "user_id_alt"
    else:
        principal_hint = ""
    return RuntimeContext(
        session_id=session_id,
        platform=_platform_from_kwargs(kwargs),
        agent_context=str(kwargs.get("agent_context", "primary") or "primary"),
        agent_identity=str(kwargs.get("agent_identity", "default") or "default"),
        agent_workspace=str(kwargs.get("agent_workspace", "") or ""),
        parent_session_id=str(kwargs.get("parent_session_id", "") or ""),
        user_id=user_id,
        user_email=user_email,
        user_name=user_name,
        user_id_alt=user_id_alt,
        principal_source=principal_hint,
        request_metadata=metadata,
        metadata_shared_intent=_metadata_shared_intent(metadata),
    )
