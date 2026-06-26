# Layered LanceDB SQLite Memory Provider

Hermes memory provider plugin that keeps SQLite as the source of truth and uses LanceDB-compatible semantic indexing for layered recall.

# Memory Specification

This is the complete, normative description of how memory is identified,
isolated, written, recalled, and migrated.

## 1. Layers

| Layer | Scope | Principal | Notes |
|---|---|---|---|
| `episodic` | session-bound turn memory | per user (or `__shared__`) | written every turn (`importance=0.35`, `source=sync_turn`) |
| `semantic_user` | durable per-user memory | the gateway user | only for identified gateway users |
| `semantic_shared` | durable workspace memory | `__shared__` | shared across all users in the workspace |

## 2. Identity resolution

Identity is read from request kwargs in this **field priority**: explicit kwarg
value → `X-Hermes-*` header → `X-OpenWebUI-*` header.

Header sources accepted (any of): `headers`, `request_headers`,
`hermes_headers`, `openwebui_headers`.

| Field | Hermes header | OpenWebUI header |
|---|---|---|
| user email | `X-Hermes-User-Email` | `X-OpenWebUI-User-Email` |
| user id | `X-Hermes-User-Id` | `X-OpenWebUI-User-Id` |
| user name | `X-Hermes-User-Name` | `X-OpenWebUI-User-Name` |
| platform | `X-Hermes-Platform` | — |

- **Header keys are case-insensitive.** Incoming headers are canonicalized to
  lowercase, so `X-Hermes-User-Id`, `x-hermes-user-id`, and `X-HERMES-USER-ID`
  are equivalent. Header **values** are preserved as-is (platform values are
  case-sensitive, e.g. `wechat` ≠ `WeChat`).
- **Body fallback:** for gateway-ish requests lacking headers, identity may be
  parsed from a `# Current User` block in a system message.
- **Sidecar fallback:** `identity_sidecar` caches identity per `session_id`.

## 3. Gateway classification

A request is treated as a **gateway** request (private isolation) if **any** of:

1. it carries an identity (`user_email`, `user_id`, or `user_id_alt`), or
2. `platform` is non-empty and not `cli`, or
3. `platform` is in `gateway_platforms` (legacy allowlist, kept for
   compatibility).

Otherwise it is a **non-gateway / CLI** request and uses shared memory.

> Note: `platform` is a free-form, caller-defined value (e.g.
> `wechat_miniprogram`). Classification no longer depends on the allowlist
> alone, so arbitrary platform values are isolated correctly.

## 4. Principal (isolation key)

`principal_id` is the per-user isolation key:

- **Gateway, identifiable:** `user_email` → (`user_id_alt` if
  `prefer_user_id_alt`) → `user_id` → `user_id_alt`.
- **Gateway, not identifiable:** `__shared__`. A request that comes through the
  gateway but whose user cannot be identified is classified into **shared
  memory**.
- **Non-gateway:** `__shared__`.

### 4b. Persisted identity (`user_id` / `user_email` / `user_name`)

- The resolved identity is stored on **every** memory row in three dedicated
  columns (`user_id`, `user_email`, `user_name`), in addition to the derived
  `principal_id` isolation key.
- This makes a memory traceable to its author even when `principal_id` is an
  opaque id rather than an email. Recall records carry these fields directly.
- Values are stamped from the request `NamespaceContext` on every write path
  (turn sync, builtin/mirrored writes, daily compaction). Rows written without
  an identifiable user (e.g. shared memory) keep the empty-string default.

## 5. Platform dimension (first-class field)

- Resolved as `kwargs["platform"]` → `X-Hermes-Platform` header → `cli`.
- Stored on **every** memory row (`memories.platform`) and in the LanceDB
  index, for any arbitrary value.
- **Does not affect `principal_id`.** The same user's memory is unified across
  platforms by default.
- `recall_platform_scoped=true` restricts recall of a user's own memory to the
  current platform; the shared workspace pool stays cross-platform.

## 5b. Expiry (`expires_at`)

- Each memory row carries an `expires_at` field: an ISO 8601 UTC timestamp
  string. An empty string (`''`, the default) means **never expires**.
- At recall time, every `status='active'` query is additionally filtered by
  `(expires_at = '' OR expires_at > :now)` where `:now = utc_now()`. Expired
  memories are **excluded from recall but not physically deleted** — they remain
  in the table with their original `status='active'` and are fully auditable.
- `insert_memory` accepts an optional `expires_at` keyword argument. When the
  config option `default_ttl_hours > 0`, memories written without an explicit
  `expires_at` are stamped with `now + default_ttl_hours`.
- The `purge-expired` CLI command archives expired memories
  (`status='archived'`) on demand; it is a dry run by default.

## 6. Isolation namespace

Every record is partitioned by:
`profile_id` (= `agent_identity`) → `workspace_id` (= `agent_workspace` /
`memory_workspace`) → `principal_id` → `session_id` (episodic only) → `layer`.

## 7. Write policy

- Only `primary` contexts write durable memory by default; non-primary writes
  are gated by `allow_non_primary_durable_writes`.
- Promotion (`governance.classify_turn`): explicit memory phrases →
  `confidence 0.96`; non-transient statements with ≥6 words → `0.52`; durable
  promotion requires `confidence ≥ promotion_min_score` (default `0.8`).
- Shared writes require the `user_email` to be in `shared_writer_emails` **and**
  explicit shared intent (when `shared_explicit_required`).
- Duplicate detection uses content fingerprints; near-duplicates (≥0.75 word
  overlap) supersede the older record.

## 8. Recall routing

- **Gateway user (identifiable):** session `episodic` + today's cross-session
  `episodic` + `semantic_user` + `semantic_shared`.
- **Non-gateway / not identifiable:** session `episodic` + `semantic_shared`.
- Non-primary contexts can read but do not promote durable memory by default.

## 9. Legacy data classification & migration

- Gateway history with **no identifiable user** belongs in **shared memory**
  (`__shared__`) — identical to the current principal rule above.
- The `platform` column is added automatically to existing databases on the
  next start (see [Upgrading](#upgrading)); legacy rows get `platform=''` and
  can be backfilled from provenance via `backfill-platform`.

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
- `recall_platform_scoped` (default `false`: cross-platform unified recall;
  `true`: restrict a user's own-memory recall to the current platform)
- `default_ttl_hours` (default `0` = never expire; when > 0, memories written
  without an explicit `expires_at` get `now + default_ttl_hours`)

## CLI

The provider exposes a small maintenance CLI when active:

```bash
hermes layered_lancedb_sqlite validate
hermes layered_lancedb_sqlite rebuild-index
hermes layered_lancedb_sqlite backfill-platform --profile coder --workspace workspace-a            # dry run
hermes layered_lancedb_sqlite backfill-platform --profile coder --workspace workspace-a --apply    # commit
hermes layered_lancedb_sqlite compact-user --profile coder --workspace workspace-a --date 2026-05-28 --user-email doris@example.com
hermes layered_lancedb_sqlite compact-daily --profile coder --workspace workspace-a --date 2026-05-28
hermes layered_lancedb_sqlite purge-expired --profile coder --workspace workspace-a            # dry run, reports counts
hermes layered_lancedb_sqlite purge-expired --profile coder --workspace workspace-a --apply    # archive expired memories
```

Daily user maintenance is explicitly triggered by Hermes or an external
scheduler. The provider does not start an internal timer. Per-user maintenance
uses Gateway identity fields (`user_email` or `user_id`) to resolve the same
private principal used by normal Gateway memory, reads and writes only that
principal's `semantic_user` scope, and records idempotent maintenance state per
profile/workspace/principal/date. Shared workspace memory maintenance is kept
separate from per-user maintenance.

## Upgrading

### 0.4.x → 0.5.0 (persisted identity columns)

Backward compatible. Migration runs automatically and idempotently on the next
provider `initialize()`:

- `memories.user_id`, `memories.user_email`, and `memories.user_name` columns
  are added to existing databases (`ALTER TABLE`), defaulting to `''`.
- No semantic index rebuild is required — the LanceDB schema is untouched.

Existing rows keep empty identity fields; new writes are stamped from the
request identity going forward. There is no backfill (the raw identity for
historical rows was never persisted). See
[Persisted identity](#4b-persisted-identity-user_id--user_email--user_name).

### 0.3.x → 0.4.0 (expires_at memory expiry)

No manual script is required. On the next provider `initialize()`:

- `memories.expires_at` column (`TEXT NOT NULL DEFAULT ''`) is added to
  existing databases via the idempotent `_ensure_column` migration. Existing
  rows get `expires_at=''` (never expires) and remain fully recallable.
- **No LanceDB schema change, no dimension change, no index rebuild needed.**

Optionally:

- Set `default_ttl_hours` > 0 in config to auto-stamp expiry on new writes.
- Run `purge-expired` to archive memories whose `expires_at` has passed
  (dry run by default; `--apply` to commit).

### 0.2.x → 0.3.0 (X-Hermes-* identity + platform isolation)

No manual script is required for a standard upgrade. Migrations run
automatically and idempotently on the next provider `initialize()`:

- `memories.platform` column is added to existing databases (`ALTER TABLE`).
- The `idx_memories_platform` index is created.
- `EMBEDDER_VERSION` bumps to `v2`, triggering a one-time semantic index
  rebuild so LanceDB carries the new schema.

Steps:

1. Deploy the new code and restart the provider — auto-migration completes on
   start.
2. (Optional) Backfill `platform` for legacy rows from provenance:

   ```bash
   hermes layered_lancedb_sqlite backfill-platform --profile <p> --workspace <w>          # dry run, reports counts
   hermes layered_lancedb_sqlite backfill-platform --profile <p> --workspace <w> --apply  # commit + re-sync index
   ```

Caveats:

- Legacy rows get `platform=''`. Backfill recovers the real value from
  `provenance.platform` (preserved at write time). Rows whose provenance also
  lacks a platform are reported as `remaining_empty` and stay empty.
- If you enable `recall_platform_scoped=true`, legacy rows with `platform=''`
  will not match a platform-scoped recall — backfill first, or keep the default
  `false`.
- Behavior change: requests previously misclassified as CLI (a custom platform
  not in the allowlist) are now isolated per user. Memory already written to
  `__shared__` is **not** moved automatically; gateway history with no
  identifiable user remains shared by design.

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
- `maintenance_service.py`: externally triggered per-user daily maintenance,
  idempotent state tracking, and deterministic compaction
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
