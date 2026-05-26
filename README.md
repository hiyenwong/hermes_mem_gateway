# Hermes Layered Memory Provider

Hermes memory provider plugin with:

- SQLite as the source of truth
- LanceDB-backed semantic retrieval
- layered memory isolation by workspace, user, and session

This repo implements a Hermes external memory provider for gateway and non-gateway usage. The provider keeps short-lived conversational state separate from durable user and shared memory, and it treats vector search as an index over canonical SQLite records rather than the primary store.

## Status

Current implementation includes:

- `episodic` session memory
- `semantic_user` durable gateway user memory
- `semantic_shared` durable workspace memory
- namespace routing from `memory_workspace`, `user_id`, `session_id`, and runtime context
- conservative promotion, supersession, archival, and provenance tracking
- OpenSpec change archived and synced into main specs

## Repository Layout

```text
plugins/memory/layered_lancedb_sqlite/
  __init__.py      Provider entry point and Hermes lifecycle hooks
  storage.py       SQLite store and semantic index integration
  namespace.py     Workspace/user/session routing
  governance.py    Memory classification and promotion rules
  config.py        Provider configuration and persistence
  cli.py           Validation and index rebuild helpers
  plugin.yaml      Hermes plugin manifest

openspec/specs/
  layered-memory-provider/
  memory-lifecycle-governance/
  memory-namespace-routing/

tests/
  test_provider.py
```

## Memory Model

- `episodic`
  Session-scoped turn memory. Written immediately during `sync_turn()`.
- `semantic_user`
  Durable user memory for gateway contexts with stable `user_id`.
- `semantic_shared`
  Durable shared memory for non-gateway contexts and workspace-wide knowledge.

Recall is layered:

1. current session episodic memory
2. same-user semantic memory when gateway identity is available
3. workspace shared semantic memory

## Storage

Canonical records are stored under:

- `<hermes_home>/memory-providers/layered_lancedb_sqlite/<profile>/<workspace>/memory.sqlite3`
- `<hermes_home>/memory-providers/layered_lancedb_sqlite/<profile>/<workspace>/lancedb/`

If `lancedb` is unavailable, the provider falls back to a local stub index while preserving the rebuild contract from SQLite.

## Configuration

Saved at:

- `<hermes_home>/memory-providers/layered_lancedb_sqlite/config.yaml`
- `<hermes_home>/.env`
- `<hermes_home>/profiles/<profile_id>/.env`

Primary options:

- `memory_workspace`
- `profile_id`
- `allow_non_primary_durable_writes`
- `promotion_min_score`
- `gateway_platforms`
- `embedding_dimensions`

Environment variable overrides use the `LAYERED_MEMORY_` prefix, for example:

```dotenv
LAYERED_MEMORY_WORKSPACE=project-a
LAYERED_MEMORY_PROFILE_ID=coder
LAYERED_MEMORY_PROMOTION_MIN_SCORE=0.85
```

Supported `.env` locations:

- `<hermes_home>/.env`
- `<hermes_home>/profiles/<profile_id>/.env`

Configuration precedence is:

1. runtime `agent_workspace` / `agent_identity`
2. profile `.env`
3. `<hermes_home>/.env`
4. `config.yaml`
5. built-in defaults

## Development

Install dependencies:

```bash
pip install -e .[dev]
```

Run tests:

```bash
pytest -q
```

## Plugin Usage

The provider package lives in:

- [plugins/memory/layered_lancedb_sqlite/README.md](/Users/hiyenwong/projects/ai_projects/hermes/hermes_mem_gateway/plugins/memory/layered_lancedb_sqlite/README.md)

Maintenance commands:

```bash
hermes layered_lancedb_sqlite validate
hermes layered_lancedb_sqlite rebuild-index
```

## OpenSpec History

The implementation was developed from an OpenSpec change and archived after spec sync:

- archived change:
  [openspec/changes/archive/2026-05-26-add-layered-lancedb-sqlite-memory-provider](/Users/hiyenwong/projects/ai_projects/hermes/hermes_mem_gateway/openspec/changes/archive/2026-05-26-add-layered-lancedb-sqlite-memory-provider)

Main synced specs:

- [openspec/specs/layered-memory-provider/spec.md](/Users/hiyenwong/projects/ai_projects/hermes/hermes_mem_gateway/openspec/specs/layered-memory-provider/spec.md)
- [openspec/specs/memory-lifecycle-governance/spec.md](/Users/hiyenwong/projects/ai_projects/hermes/hermes_mem_gateway/openspec/specs/memory-lifecycle-governance/spec.md)
- [openspec/specs/memory-namespace-routing/spec.md](/Users/hiyenwong/projects/ai_projects/hermes/hermes_mem_gateway/openspec/specs/memory-namespace-routing/spec.md)
