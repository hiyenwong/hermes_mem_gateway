# Layered LanceDB SQLite Memory Provider

Hermes memory provider plugin that keeps SQLite as the source of truth and uses LanceDB-compatible semantic indexing for layered recall.

## Layers

- `episodic`: session-bound turn memory
- `semantic_user`: durable gateway user memory
- `semantic_shared`: durable workspace memory

## Routing

- Gateway primary contexts with stable `user_id` read from `episodic + semantic_user + semantic_shared`
- Non-gateway primary contexts read from `episodic + semantic_shared`
- Non-primary contexts can read, but durable promotion is blocked by default

## Storage

The provider stores canonical records in:

- `<hermes_home>/memory-providers/layered_lancedb_sqlite/<profile>/<workspace>/memory.sqlite3`
- `<hermes_home>/memory-providers/layered_lancedb_sqlite/<profile>/<workspace>/lancedb/`

If `lancedb` is unavailable, the provider falls back to a local semantic-index stub while keeping the same rebuild contract from SQLite.

## Setup

Place this directory under `$HERMES_HOME/plugins/memory/layered_lancedb_sqlite/` or install this repo as a package and point Hermes at the plugin directory.

Configuration is saved into:

- `<hermes_home>/memory-providers/layered_lancedb_sqlite/config.yaml`

Key options:

- `memory_workspace`
- `profile_id`
- `allow_non_primary_durable_writes`
- `promotion_min_score`
- `gateway_platforms`
- `embedding_dimensions`

## CLI

The provider exposes a small maintenance CLI when active:

```bash
hermes layered_lancedb_sqlite validate
hermes layered_lancedb_sqlite rebuild-index
```

## Architecture Notes

The canonical implementation lives under:

- `plugins/memory/layered_lancedb_sqlite/`

Root-level modules are compatibility shims only. They import from the canonical
plugin package and do not own provider, policy, namespace, governance, storage,
or CLI behavior.

The provider internals are split into focused modules:

- `policy.py`: shared intent, durable write, target layer, principal, and recall
  scope decisions
- `recall_service.py`: layered recall assembly and reinforcement
- `promotion_service.py`: turn consolidation, durable promotion, duplicate
  detection, and supersession
- `memory_write_service.py`: explicit memory write mirroring
- `prompt_format.py`: memory and Gateway user context formatting
- `background.py`: pending future tracking, draining, and background error
  capture

The OpenSpec implementation plan is tracked at:

- `openspec/changes/refactor-memory-provider-architecture/`

### Implemented Refactor Scope

This architecture pass addressed:

- Single source of implementation
- Centralized policy decisions
- Thinner provider orchestration

### 1. Single Source Of Implementation

- `plugins/memory/layered_lancedb_sqlite/` is the canonical source.
- Root-level duplicate modules now delegate to the canonical plugin package.
- Tests assert the provider class comes from
  `plugins.memory.layered_lancedb_sqlite`.

### 2. Policy Centralization

- `policy.py` owns shared intent, shared authorization, durable write target
  decisions, principal selection, recall scopes, and audit metadata.
- `namespace.py` resolves context facts.
- `governance.py` handles candidate extraction, confidence, ranking,
  fingerprinting, and supersession heuristics.
- Table-driven policy tests cover Gateway, CLI, primary, non-primary,
  allowlisted, non-allowlisted, metadata intent, and natural-language intent.

### 3. Provider Thinning

- `LayeredLanceDBSQLiteMemoryProvider` remains the Hermes-facing adapter.
- Recall, promotion, explicit writes, prompt formatting, and background task
  handling are delegated to focused modules.
- Public provider hooks and storage layout remain unchanged.
