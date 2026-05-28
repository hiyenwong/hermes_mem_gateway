from __future__ import annotations

from typing import Any, Dict, List, Optional

from .background import BackgroundTasks
from .config import ProviderConfig, load_config, load_env_overrides, merge_overrides, save_config as persist_config
from .governance import fingerprint_text
from .memory_write_service import mirror_memory
from .namespace import NamespaceContext, resolve_namespace, runtime_from_kwargs
from .promotion_service import consolidate_turn
from .recall_service import assemble_recall
from .storage import SQLiteStore

try:  # pragma: no cover - Hermes runtime dependency
    from agent.memory_provider import MemoryProvider
except Exception:  # pragma: no cover
    class MemoryProvider:  # type: ignore[override]
        pass


class LayeredLanceDBSQLiteMemoryProvider(MemoryProvider):
    def __init__(self) -> None:
        self._hermes_home = ""
        self._config = ProviderConfig()
        self._runtime = runtime_from_kwargs("default")
        self._namespace = resolve_namespace(self._config, self._runtime)
        self._store: SQLiteStore | None = None
        self._background = BackgroundTasks()
        self._prefetch_cache: dict[tuple[str, str, str, str], str] = {}

    @property
    def name(self) -> str:
        return "layered_lancedb_sqlite"

    def is_available(self) -> bool:
        return True

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return []

    def handle_tool_call(self, name: str, args: Dict[str, Any]) -> str:
        raise RuntimeError(f"{self.name} does not expose runtime tools: {name}")

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {"key": "memory_workspace", "description": "Workspace namespace for durable memory", "default": "default"},
            {"key": "profile_id", "description": "Profile identifier for storage partitioning", "default": "default"},
            {"key": "allow_non_primary_durable_writes", "description": "Allow non-primary contexts to write durable memory", "default": False, "choices": [True, False]},
            {"key": "shared_writer_emails", "description": "Allowlisted gateway emails that may write shared memory", "default": []},
            {"key": "shared_explicit_required", "description": "Require explicit shared intent for shared writes", "default": True, "choices": [True, False]},
            {"key": "promotion_min_score", "description": "Minimum confidence for durable promotion", "default": 0.8},
            {"key": "embedding_dimensions", "description": "Semantic embedding dimensions", "default": 64},
        ]

    def save_config(self, values: Dict[str, Any], hermes_home: str) -> None:
        persist_config(values, hermes_home)

    def initialize(self, session_id: str, **kwargs) -> None:
        hermes_home = str(kwargs.get("hermes_home", ""))
        self._hermes_home = hermes_home
        base_config = load_config(hermes_home)
        profile_hint = str(kwargs.get("agent_identity") or base_config.profile_id or "default")
        env_overrides = load_env_overrides(hermes_home, profile_hint)
        self._config = merge_overrides(
            merge_overrides(base_config, env_overrides.items()),
            [
                ("profile_id", kwargs.get("agent_identity") or None),
                ("memory_workspace", kwargs.get("agent_workspace") or None),
            ],
        )
        self._runtime = runtime_from_kwargs(session_id, **kwargs)
        self._namespace = resolve_namespace(self._config, self._runtime)
        base = self._config.storage_base(hermes_home)
        self._store = SQLiteStore(base / "memory.sqlite3", dimensions=self._config.embedding_dimensions, index_path=base / "lancedb")
        self._store.bootstrap()
        self._store.ensure_index_current()

    def system_prompt_block(self) -> str:
        return (
            "Layered memory provider active. SQLite is authoritative. "
            "Recall uses session episodic, user semantic, and workspace shared semantic scopes."
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        namespace = self._active_namespace(session_id=session_id or self._namespace.session_id)
        cache_key = (
            namespace.workspace_id,
            namespace.principal_id,
            namespace.session_id,
            query,
        )
        cached = self._prefetch_cache.get(cache_key)
        if cached is not None:
            return cached
        context = assemble_recall(query, config=self._config, namespace=namespace, store=self._require_store())
        self._prefetch_cache[cache_key] = context
        return context

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        namespace = self._active_namespace(session_id=session_id or self._namespace.session_id)
        self._background.submit(assemble_recall, query, config=self._config, namespace=namespace, store=self._require_store())

    def sync_turn(self, user: str, assistant: str, *, session_id: str = "") -> None:
        store = self._require_store()
        explicit_session_id = session_id or self._namespace.session_id
        namespace = self._active_namespace(session_id=explicit_session_id)
        episodic_id = store.insert_memory(
            profile_id=namespace.profile_id,
            workspace_id=namespace.workspace_id,
            principal_id=namespace.principal_id,
            session_id=namespace.session_id,
            layer="episodic",
            kind="turn",
            content=f"USER: {user}\nASSISTANT: {assistant}",
            fingerprint=fingerprint_text(f"{user}\n{assistant}"),
            source="sync_turn",
            importance=0.35,
            metadata={"platform": namespace.platform, "agent_context": namespace.agent_context},
        )
        store.add_provenance(
            episodic_id,
            source_type="sync_turn",
            source_ref=namespace.session_id,
            platform=namespace.platform,
            agent_context=namespace.agent_context,
            session_id=namespace.session_id,
        )
        if session_id and session_id != self._runtime.session_id:
            return
        self._background.submit(
            consolidate_turn,
            store=store,
            config=self._config,
            namespace=namespace,
            user=user,
            assistant=assistant,
        )

    def on_session_switch(self, new_session_id: str, *, parent_session_id: str = "", reset: bool = False, **kwargs) -> None:
        self._background.drain(timeout=5)
        merged = {
            "platform": kwargs.get("platform", self._runtime.platform),
            "agent_context": kwargs.get("agent_context", self._runtime.agent_context),
            "agent_identity": kwargs.get("agent_identity", self._runtime.agent_identity),
            "agent_workspace": kwargs.get("agent_workspace", self._runtime.agent_workspace),
            "parent_session_id": parent_session_id or self._runtime.parent_session_id,
            "user_id": kwargs.get("user_id", self._runtime.user_id),
            "user_email": kwargs.get("user_email", self._runtime.user_email),
            "user_name": kwargs.get("user_name", self._runtime.user_name),
            "request_metadata": kwargs.get("request_metadata", self._runtime.request_metadata),
            "metadata": kwargs.get("metadata", self._runtime.request_metadata),
            "headers": kwargs.get("headers", None),
            "request_headers": kwargs.get("request_headers", None),
            "openwebui_headers": kwargs.get("openwebui_headers", None),
        }
        self._runtime = runtime_from_kwargs(new_session_id, **merged)
        self._namespace = resolve_namespace(self._config, self._runtime)
        if reset:
            self._prefetch_cache = {key: value for key, value in self._prefetch_cache.items() if key[2] != new_session_id}

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        if not messages:
            return
        summary_parts = []
        for message in messages[-4:]:
            role = str(message.get("role", "unknown")).upper()
            content = str(message.get("content", ""))
            summary_parts.append(f"{role}: {content}")
        self._background.submit(
            mirror_memory,
            store=self._require_store(),
            config=self._config,
            namespace=self._namespace,
            target="memory",
            content="\n".join(summary_parts),
            source="session_end_summary",
        )

    def on_pre_compress(self, messages: List[Dict[str, Any]]) -> str:
        if not messages:
            return ""
        latest = str(messages[-1].get("content", ""))
        return self.prefetch(latest)

    def on_memory_write(
        self,
        action: str,
        target: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if action == "remove":
            return
        self._background.submit(
            mirror_memory,
            store=self._require_store(),
            config=self._config,
            namespace=self._namespace,
            target=target,
            content=content,
            source=f"memory_write:{action}:{target}",
            metadata=metadata or {},
        )

    def shutdown(self) -> None:
        self._background.drain(timeout=5)
        self._background.shutdown()
        if self._store is not None:
            self._store.close()
            self._store = None

    def post_setup(self, hermes_home: str, config: Dict[str, Any]) -> None:
        self.save_config(config, hermes_home)

    def validate_storage(self) -> dict[str, Any]:
        result = self._require_store().validate()
        result["background_error_count"] = len(self._background.errors)
        return result

    def rebuild_index(self) -> int:
        return self._require_store().rebuild_index()

    def _active_namespace(self, *, session_id: str | None = None) -> NamespaceContext:
        runtime = self._runtime
        if session_id and session_id != runtime.session_id:
            runtime = runtime_from_kwargs(
                session_id,
                platform=runtime.platform,
                agent_context=runtime.agent_context,
                agent_identity=runtime.agent_identity,
                agent_workspace=runtime.agent_workspace,
                parent_session_id=runtime.parent_session_id,
                user_id=runtime.user_id,
                user_email=runtime.user_email,
                user_name=runtime.user_name,
                request_metadata=runtime.request_metadata,
            )
            return resolve_namespace(self._config, runtime)
        return self._namespace

    def _require_store(self) -> SQLiteStore:
        if self._store is None:
            raise RuntimeError("Provider not initialized")
        return self._store


def register(ctx=None) -> LayeredLanceDBSQLiteMemoryProvider:
    return LayeredLanceDBSQLiteMemoryProvider()
