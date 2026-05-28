from __future__ import annotations

import inspect

import pytest

from plugins.memory.layered_lancedb_sqlite import LayeredLanceDBSQLiteMemoryProvider
from plugins.memory.layered_lancedb_sqlite.background import BackgroundTasks
from plugins.memory.layered_lancedb_sqlite.config import ProviderConfig
from plugins.memory.layered_lancedb_sqlite.namespace import SHARED_PRINCIPAL, resolve_namespace, runtime_from_kwargs
from plugins.memory.layered_lancedb_sqlite.policy import (
    memory_write_decision,
    promotion_write_decision,
    recall_scopes,
    resolve_shared_intent,
)
from plugins.memory.layered_lancedb_sqlite.prompt_format import format_memory_block


def namespace_for(config: ProviderConfig, **kwargs):
    return resolve_namespace(config, runtime_from_kwargs("session-1", **kwargs))


def test_provider_implementation_uses_canonical_plugin_package() -> None:
    source_path = inspect.getfile(LayeredLanceDBSQLiteMemoryProvider)
    assert "plugins/memory/layered_lancedb_sqlite/__init__.py" in source_path
    assert LayeredLanceDBSQLiteMemoryProvider.__module__ == "plugins.memory.layered_lancedb_sqlite"


@pytest.mark.parametrize(
    ("config", "kwargs", "content", "expected_allowed", "expected_layer", "expected_principal", "expected_reason"),
    [
        (
            ProviderConfig(),
            {"platform": "gateway", "user_id": "user-1"},
            "Remember that I prefer coffee.",
            True,
            "semantic_user",
            "user-1",
            "gateway_private_user",
        ),
        (
            ProviderConfig(shared_writer_emails=["admin@example.com"]),
            {"platform": "gateway", "user_email": "admin@example.com", "request_metadata": {"shared_memory": True}},
            "Remember that the shared deployment checklist lives in Notion.",
            True,
            "semantic_shared",
            SHARED_PRINCIPAL,
            "shared_authorized",
        ),
        (
            ProviderConfig(shared_writer_emails=["admin@example.com"]),
            {"platform": "gateway", "user_email": "admin@example.com", "request_metadata": {"shared_memory": False}},
            "Remember this as shared: the staging API base URL is https://api.internal.example.",
            True,
            "semantic_user",
            "admin@example.com",
            "gateway_private_user",
        ),
        (
            ProviderConfig(),
            {"platform": "gateway", "agent_context": "subagent", "user_id": "user-1"},
            "Remember that my legal name is Alicia Example.",
            False,
            None,
            None,
            "non_primary_blocked",
        ),
        (
            ProviderConfig(),
            {"platform": "cli"},
            "Remember that the deployment window is Fridays at 5 PM UTC.",
            True,
            "semantic_shared",
            SHARED_PRINCIPAL,
            "non_gateway_shared",
        ),
    ],
)
def test_promotion_policy_decision_matrix(
    config: ProviderConfig,
    kwargs: dict[str, object],
    content: str,
    expected_allowed: bool,
    expected_layer: str | None,
    expected_principal: str | None,
    expected_reason: str,
) -> None:
    decision = promotion_write_decision(config, namespace_for(config, **kwargs), content=content)
    assert decision.allowed is expected_allowed
    assert decision.layer == expected_layer
    assert decision.principal_id == expected_principal
    assert decision.reason == expected_reason
    assert decision.metadata["policy_reason"] == expected_reason


def test_memory_write_policy_blocks_non_primary_by_default() -> None:
    config = ProviderConfig()
    namespace = namespace_for(config, platform="cli", agent_context="subagent")

    decision = memory_write_decision(
        config,
        namespace,
        target="memory",
        content="The team deploys from a restricted jump host.",
    )

    assert decision.allowed is False
    assert decision.reason == "non_primary_blocked"


def test_shared_intent_metadata_overrides_natural_language() -> None:
    decision = resolve_shared_intent("Remember this as shared: keep it private.", False)
    assert decision.requested is False
    assert decision.source == "metadata"


def test_recall_scopes_are_explicit_and_ordered() -> None:
    config = ProviderConfig()
    namespace = namespace_for(config, platform="gateway", user_id="user-1")

    scopes = recall_scopes(namespace)

    assert [(scope.title, scope.layer, scope.principal_id) for scope in scopes] == [
        ("Session episodic memory", "episodic", "user-1"),
        ("Today's cross-session memory", "episodic", "user-1"),
        ("User semantic memory", "semantic_user", "user-1"),
        ("Workspace shared memory", "semantic_shared", SHARED_PRINCIPAL),
    ]


def test_prompt_formatter_preserves_memory_context_shape() -> None:
    assert format_memory_block("Session episodic memory", [{"content": "hello"}]) == (
        "<memory-context>\nSession episodic memory:\n1. hello\n</memory-context>"
    )


def test_background_tasks_records_errors() -> None:
    tasks = BackgroundTasks()

    def fail() -> None:
        raise RuntimeError("background failure")

    tasks.submit(fail)
    with pytest.raises(RuntimeError):
        tasks.drain(timeout=5)
    tasks.shutdown()

    assert tasks.errors
