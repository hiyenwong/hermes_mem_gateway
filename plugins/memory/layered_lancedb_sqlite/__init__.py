from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from .config import ProviderConfig, load_config, merge_overrides, save_config as persist_config
from .governance import classify_turn, find_superseded, fingerprint_text, rank_record, select_durable_layer
from .namespace import SHARED_PRINCIPAL, NamespaceContext, resolve_namespace, runtime_from_kwargs
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
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="layered-memory")
        self._pending: list[Future[Any]] = []
        self._prefetch_cache: dict[tuple[str, str, str, str], str] = {}
        self._lock = Lock()

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
            {"key": "promotion_min_score", "description": "Minimum confidence for durable promotion", "default": 0.8},
            {"key": "embedding_dimensions", "description": "Semantic embedding dimensions", "default": 64},
        ]

    def save_config(self, values: Dict[str, Any], hermes_home: str) -> None:
        persist_config(values, hermes_home)

    def initialize(self, session_id: str, **kwargs) -> None:
        hermes_home = str(kwargs.get("hermes_home", ""))
        self._hermes_home = hermes_home
        self._config = merge_overrides(
            load_config(hermes_home),
            [
                ("profile_id", kwargs.get("agent_identity")),
                ("memory_workspace", kwargs.get("agent_workspace")),
            ],
        )
        self._runtime = runtime_from_kwargs(session_id, **kwargs)
        self._namespace = resolve_namespace(self._config, self._runtime)
        base = self._config.storage_base(hermes_home)
        self._store = SQLiteStore(base / "memory.sqlite3", dimensions=self._config.embedding_dimensions, index_path=base / "lancedb")
        self._store.bootstrap()
        self._store.rebuild_index()

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
        context = self._assemble_recall(query, namespace)
        self._prefetch_cache[cache_key] = context
        return context

    def queue_prefetch(self, query: str) -> None:
        namespace = self._active_namespace()
        future = self._executor.submit(self._assemble_recall, query, namespace)
        self._pending.append(future)

    def sync_turn(self, user: str, assistant: str) -> None:
        store = self._require_store()
        namespace = self._active_namespace()
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
        self._pending.append(self._executor.submit(self._consolidate_turn, namespace, user, assistant))

    def on_session_switch(self, new_session_id: str, *, parent_session_id: str = "", reset: bool = False, **kwargs) -> None:
        self._drain_pending(timeout=5)
        merged = {
            "platform": kwargs.get("platform", self._runtime.platform),
            "agent_context": kwargs.get("agent_context", self._runtime.agent_context),
            "agent_identity": kwargs.get("agent_identity", self._runtime.agent_identity),
            "agent_workspace": kwargs.get("agent_workspace", self._runtime.agent_workspace),
            "parent_session_id": parent_session_id or self._runtime.parent_session_id,
            "user_id": kwargs.get("user_id", self._runtime.user_id),
        }
        self._runtime = runtime_from_kwargs(new_session_id, **merged)
        self._namespace = resolve_namespace(self._config, self._runtime)
        if reset:
            self._prefetch_cache = {key: value for key, value in self._prefetch_cache.items() if key[0] != new_session_id}

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        if not messages:
            return
        summary_parts = []
        for message in messages[-4:]:
            role = str(message.get("role", "unknown")).upper()
            content = str(message.get("content", ""))
            summary_parts.append(f"{role}: {content}")
        self._pending.append(
            self._executor.submit(
                self._mirror_memory,
                "\n".join(summary_parts),
                source="session_end_summary",
                target_layer="semantic_shared" if not self._namespace.is_gateway else "semantic_user",
            )
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
        target_layer = "semantic_user" if target == "user" and self._namespace.durable_user_allowed else "semantic_shared"
        self._pending.append(
            self._executor.submit(
                self._mirror_memory,
                content,
                source=f"memory_write:{action}:{target}",
                target_layer=target_layer,
                metadata=metadata or {},
            )
        )

    def shutdown(self) -> None:
        self._drain_pending(timeout=5)
        self._executor.shutdown(wait=True)
        if self._store is not None:
            self._store.close()
            self._store = None

    def post_setup(self, hermes_home: str, config: Dict[str, Any]) -> None:
        self.save_config(config, hermes_home)

    def validate_storage(self) -> dict[str, Any]:
        return self._require_store().validate()

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
            )
            return resolve_namespace(self._config, runtime)
        return self._namespace

    def _assemble_recall(self, query: str, namespace: NamespaceContext) -> str:
        store = self._require_store()
        blocks: list[str] = []
        episodic = store.search_exact(
            profile_id=namespace.profile_id,
            workspace_id=namespace.workspace_id,
            principal_id=namespace.principal_id,
            session_id=namespace.session_id,
            layer="episodic",
            limit=self._config.recall_limit_per_layer,
        )
        if episodic:
            blocks.append(self._format_block("Session episodic memory", episodic, semantic=False))

        if namespace.is_gateway and namespace.principal_id != SHARED_PRINCIPAL:
            user_hits = store.search_semantic(
                query,
                profile_id=namespace.profile_id,
                workspace_id=namespace.workspace_id,
                principal_id=namespace.principal_id,
                session_id="",
                layer="semantic_user",
                limit=self._config.recall_limit_per_layer,
            )
            if user_hits:
                blocks.append(self._format_block("User semantic memory", [hit.record for hit in user_hits]))
                for hit in user_hits:
                    store.reinforce(hit.record["id"])

        shared_hits = store.search_semantic(
            query,
            profile_id=namespace.profile_id,
            workspace_id=namespace.workspace_id,
            principal_id=SHARED_PRINCIPAL,
            session_id="",
            layer="semantic_shared",
            limit=self._config.recall_limit_per_layer,
        )
        if shared_hits:
            blocks.append(self._format_block("Workspace shared memory", [hit.record for hit in shared_hits]))
            for hit in shared_hits:
                store.reinforce(hit.record["id"])

        return "\n\n".join(blocks)

    def _format_block(self, title: str, records: list[dict[str, Any]], *, semantic: bool = True) -> str:
        lines = [f"{idx}. {record['content']}" for idx, record in enumerate(records, start=1)]
        return f"<memory-context>\n{title}:\n" + "\n".join(lines) + "\n</memory-context>"

    def _consolidate_turn(self, namespace: NamespaceContext, user: str, assistant: str) -> None:
        store = self._require_store()
        for candidate in classify_turn(user, assistant):
            layer = select_durable_layer(candidate, namespace)
            if layer is None:
                continue
            if candidate.confidence < self._config.promotion_min_score:
                continue
            existing = store.fetch_existing_durable(
                profile_id=namespace.profile_id,
                workspace_id=namespace.workspace_id,
                principal_id=namespace.principal_id if layer == "semantic_user" else SHARED_PRINCIPAL,
                layer=layer,
            )
            exact = next((row for row in existing if row["fingerprint"] == candidate.fingerprint), None)
            if exact:
                store.reinforce(exact["id"])
                continue
            supersedes_id = find_superseded(existing, candidate)
            target_principal = namespace.principal_id if layer == "semantic_user" else SHARED_PRINCIPAL
            memory_id = store.insert_memory(
                profile_id=namespace.profile_id,
                workspace_id=namespace.workspace_id,
                principal_id=target_principal,
                session_id=namespace.session_id,
                layer=layer,
                kind=candidate.kind,
                content=candidate.content,
                fingerprint=candidate.fingerprint,
                source="promotion",
                importance=candidate.confidence,
                metadata={"platform": namespace.platform, "agent_context": namespace.agent_context},
                supersedes_id=supersedes_id,
            )
            store.add_provenance(
                memory_id,
                source_type="promotion",
                source_ref=namespace.session_id,
                platform=namespace.platform,
                agent_context=namespace.agent_context,
                session_id=namespace.session_id,
            )
            if candidate.confidence < 0.9 and layer.startswith("semantic"):
                score = rank_record(candidate.confidence, reinforcement_count=0, access_count=0, archived=False)
                if score < self._config.promotion_min_score:
                    store.archive(memory_id)

    def _mirror_memory(
        self,
        content: str,
        *,
        source: str,
        target_layer: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        namespace = self._active_namespace()
        target_principal = namespace.principal_id if target_layer == "semantic_user" else SHARED_PRINCIPAL
        if target_layer == "semantic_user" and not namespace.durable_user_allowed:
            return
        if target_layer == "semantic_shared" and not namespace.durable_shared_allowed:
            return
        store = self._require_store()
        memory_id = store.insert_memory(
            profile_id=namespace.profile_id,
            workspace_id=namespace.workspace_id,
            principal_id=target_principal,
            session_id=namespace.session_id,
            layer=target_layer,
            kind="builtin_memory",
            content=content.strip(),
            fingerprint=fingerprint_text(content),
            source=source,
            importance=0.95,
            metadata=metadata or {},
        )
        store.add_provenance(
            memory_id,
            source_type="builtin_memory",
            source_ref=source,
            platform=namespace.platform,
            agent_context=namespace.agent_context,
            session_id=namespace.session_id,
            metadata=metadata or {},
        )

    def _require_store(self) -> SQLiteStore:
        if self._store is None:
            raise RuntimeError("Provider not initialized")
        return self._store

    def _drain_pending(self, *, timeout: float) -> None:
        for future in list(self._pending):
            future.result(timeout=timeout)
        self._pending.clear()


def register() -> LayeredLanceDBSQLiteMemoryProvider:
    return LayeredLanceDBSQLiteMemoryProvider()
