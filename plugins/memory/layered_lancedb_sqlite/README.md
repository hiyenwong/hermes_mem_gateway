# Layered LanceDB SQLite Memory Provider

Hermes memory provider plugin that keeps SQLite as the source of truth and uses LanceDB-compatible semantic indexing for layered recall.

## Layers

- `episodic`: session-bound turn memory
- `semantic_user`: durable gateway user memory
- `semantic_shared`: durable workspace memory

## Identity & isolation

- Identity headers, field priority `kwarg > X-Hermes-* > X-OpenWebUI-*`:
  `X-Hermes-User-Id`, `X-Hermes-User-Name`, `X-Hermes-User-Email`,
  `X-Hermes-Platform`. Header keys are case-insensitive; values are preserved.
- A request is a **gateway** request (private isolation) if it carries any
  identity, or `platform` is non-empty and not `cli`, or `platform` is in the
  legacy `gateway_platforms` allowlist.
- `principal_id` (isolation key): `user_email` → `user_id` (or `user_id_alt`).
  A gateway request whose user cannot be identified is classified into shared
  memory (`__shared__`).
- `platform` is a free-form value stored on every record as a first-class
  field. It does not change `principal_id`, so a user's memory is unified
  across platforms by default. Set `recall_platform_scoped=true` to restrict a
  user's own-memory recall to the current platform.

## Routing

- Gateway primary contexts with an identifiable user read from `episodic + semantic_user + semantic_shared`
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
- `gateway_platforms` (legacy allowlist; no longer required for isolation)
- `embedding_dimensions`
- `prefer_user_id_alt`
- `recall_platform_scoped` (default `false` = cross-platform unified recall)
- `default_ttl_hours` (default `0` = never expire; when > 0, memories written
  without an explicit `expires_at` get `now + default_ttl_hours`)

## CLI

The provider exposes a small maintenance CLI when active:

```bash
hermes layered_lancedb_sqlite validate
hermes layered_lancedb_sqlite rebuild-index
hermes layered_lancedb_sqlite backfill-platform --profile coder --workspace workspace-a [--apply]
hermes layered_lancedb_sqlite purge-expired --profile coder --workspace workspace-a [--apply]
```

## Upgrading (0.2.x → 0.3.0)

Auto-migration runs on the next `initialize()`: the `memories.platform` column
and its index are added to existing databases, and `EMBEDDER_VERSION` bumps to
`v2` to rebuild the semantic index. No manual script is required. Optionally run
`backfill-platform` to recover the real platform of legacy rows from provenance
(`--apply` to commit; dry run by default). Legacy gateway memory with no
identifiable user stays in shared memory by design.

## Architecture

The canonical implementation lives in `plugins/memory/layered_lancedb_sqlite/`.
Root-level modules in this repository are compatibility shims only.

Policy-sensitive decisions are centralized in `policy.py`; provider hooks
delegate recall, promotion, memory-write mirroring, prompt formatting, and
background task handling to focused service modules.

Daily user maintenance is exposed through explicit CLI/service operations:

```bash
hermes layered_lancedb_sqlite compact-user --profile coder --workspace workspace-a --date 2026-05-28 --user-id owui-user-42
hermes layered_lancedb_sqlite compact-daily --profile coder --workspace workspace-a --date 2026-05-28
```

Schedule these commands from Hermes or an external scheduler. Per-user
maintenance runs with Gateway identity context and writes only to the same
`semantic_user` principal; shared memory maintenance is intentionally separate.
