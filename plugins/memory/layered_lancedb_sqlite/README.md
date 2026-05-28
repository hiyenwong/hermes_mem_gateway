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

## Architecture

The canonical implementation lives in `plugins/memory/layered_lancedb_sqlite/`.
Root-level modules in this repository are compatibility shims only.

Policy-sensitive decisions are centralized in `policy.py`; provider hooks
delegate recall, promotion, memory-write mirroring, prompt formatting, and
background task handling to focused service modules.
