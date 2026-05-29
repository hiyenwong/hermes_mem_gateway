from __future__ import annotations

from typing import Any

from .config import ProviderConfig
from .namespace import NamespaceContext
from .policy import resolve_shared_intent, shared_write_allowed


def format_memory_block(title: str, records: list[dict[str, Any]]) -> str:
    lines = [
        f"{idx}. {record['content']}" for idx, record in enumerate(records, start=1)
    ]
    return f"<memory-context>\n{title}:\n" + "\n".join(lines) + "\n</memory-context>"


def gateway_prompt_context(config: ProviderConfig, namespace: NamespaceContext) -> str:
    if not namespace.is_gateway or not (
        namespace.user_name or namespace.user_email or namespace.user_id
    ):
        return ""
    shared_intent = resolve_shared_intent("", namespace.metadata_shared_intent)
    shared_authorized = shared_write_allowed(config, namespace, shared_intent)
    lines = [
        "<user-context>",
        "Gateway user context:",
        "- authenticated_user: true",
    ]
    if namespace.user_name:
        lines.append(f"- display_name: {namespace.user_name}")
    lines.extend(
        [
            "- memory_scope: private",
            f"- shared_write_requested: {'true' if shared_intent.requested else 'false'}",
            f"- shared_write_allowed: {'true' if shared_authorized else 'false'}",
        ]
    )
    if shared_intent.requested:
        lines.append(f"- shared_request_source: {shared_intent.source}")
    lines.append("</user-context>")
    return "\n".join(lines)
