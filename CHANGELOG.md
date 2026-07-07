# Changelog

All notable changes to this project are documented in this file.

## 0.6.0 - 2026-07-05

### Added

- Adapted the provider to the Hermes 0.18 (`v2026.7.1`) `MemoryProvider`
  contract:
  - `on_session_switch()` now accepts the new `rewound: bool = False`
    parameter. When `rewound=True` (fired by `/undo`), the prefetch cache
    entries keyed on the rewound session are evicted so the next recall is
    assembled against the shortened transcript rather than a stale cached
    result. The existing `reset=True` path (`/new`, `/reset`) also benefits:
    when `parent_session_id` is supplied, the old session's cached recall is
    now correctly dropped instead of lingering in memory.
  - `backup_paths()` returns an explicit empty list. All provider state
    (SQLite, LanceDB, config) lives under `HERMES_HOME`, so there is nothing
    external to declare; the explicit override documents the invariant and
    makes it testable.
- New tests cover the rewound invalidation path, the reset-with-parent
  cache drop, the `backup_paths()` contract, and the synchronous
  consolidation semantics.

### Changed

- `sync_turn()` now runs `consolidate_turn()` synchronously instead of
  dispatching it to the internal background pool. Hermes 0.18 invokes
  `sync_turn` on a background worker inside `MemoryManager` already, so the
  second layer of backgrounding was redundant and prevented the manager's
  `flush_pending()` barrier from capturing the full write (episodic +
  promotion). The episodic insert and durable promotion are now both
  committed before `sync_turn()` returns.
- `on_session_end()` and `on_memory_write()` still use the internal
  background pool — those hooks are invoked on the caller's thread by the
  manager, so they must remain non-blocking.

### Migration (0.5.x → 0.6.0)

No schema changes, no index rebuild. The release is a drop-in replacement:

- The new `rewound` parameter on `on_session_switch` has a default value, so
  the provider continues to work against older Hermes runtimes (they simply
  never pass it).
- The synchronous `sync_turn` change is internal behaviour only; callers do
  not need to adjust.

### Verified

- `ruff check --fix` and `ruff format`
- `pytest -q` (97 passed)

## 0.5.0 - 2026-06-26

### Added

- Persist resolved identity on every memory row: new `user_id`, `user_email`,
  and `user_name` columns (all `TEXT NOT NULL DEFAULT ''`). They are stamped at
  write time from the request `NamespaceContext` across all write paths
  (`sync_turn`, `mirror_memory`, daily compaction), so a memory can be traced to
  the user even when `principal_id` is an opaque id. Recall records carry the
  fields automatically via `_row_to_dict`.

### Migration

- The three identity columns are added to existing databases automatically and
  idempotently via `ALTER TABLE` on the next `initialize()`; legacy rows default
  to `''`. No semantic index rebuild is required. See README "Upgrading: 0.4.x →
  0.5.0".

## 0.4.0 - 2026-06-24

### Added

- Introduced `expires_at` field on the `memories` table: an ISO 8601 UTC
  timestamp string. An empty string (`''`, the default) means "never expires"
  (backward compatible). Memories whose `expires_at` has passed are
  automatically excluded from recall — they are not returned by any recall path
  (`fetch_existing_durable`, `search_exact`, `search_semantic`,
  `eligible_index_rows`, `fetch_user_records_for_date`), but they are **not
  physically deleted**, preserving auditability.
- Added `expires_at` optional keyword to `SQLiteStore.insert_memory` so callers
  can stamp an expiry at write time.
- Added `default_ttl_hours` config option (default `0` = no expiry). When > 0,
  memories written without an explicit `expires_at` get one computed as
  `now + default_ttl_hours`.
- Added `purge-expired` CLI command: archives memories whose `expires_at` has
  passed (sets `status='archived'`). Dry-run by default; `--apply` to commit.

### Migration (0.3.x → 0.4.0)

- No manual script required. On the next provider `initialize()` the
  `memories.expires_at` column is added to existing databases via
  `_ensure_column` (idempotent `ALTER TABLE`). Existing rows get
  `expires_at=''` (never expires) and remain fully recallable.
- **No LanceDB schema change, no dimension change, no index rebuild needed.**
- Optionally run `purge-expired` to clean up if you later write TTL'd memories.

### Verified

- `ruff check --fix` and `ruff format`
- `pytest tests/` (full suite, deterministic on both stub and LanceDB backends)

## 0.3.1 - 2026-06-24

### Fixed

- Made `test_semantic_search_skips_rows_with_stale_vector_dimensions`
  deterministic by forcing the stub backend via monkeypatch. The stale-dimension
  guard in `SemanticIndex.search` is only reachable on the stub backend; with
  LanceDB installed, the fixed-width vector schema rejected the mismatched vector
  at upsert time, so the test failed (or silently passed without exercising the
  guard) depending on whether `lancedb` was present. Test-only change; no runtime
  behavior affected.

## 0.3.0 - 2026-06-24

### Added

- Recognize `X-Hermes-*` identity headers (`X-Hermes-User-Id`,
  `X-Hermes-User-Name`, `X-Hermes-User-Email`, `X-Hermes-Platform`) with
  priority over `X-OpenWebUI-*`. Header matching is case-insensitive.
- Promoted `platform` to a first-class field: `memories.platform` column,
  `idx_memories_platform` index, and LanceDB schema field; stored on every write.
- Added `recall_platform_scoped` config option (default `false`) to restrict a
  user's own-memory recall to the current platform.
- Added `backfill-platform` CLI command to recover legacy rows' platform from
  provenance (dry run by default, `--apply` to commit and re-sync the index).
- Added tests for header identity/priority, case-insensitivity, gateway
  classification with arbitrary platforms, platform as a first-class field,
  cross-platform unified vs scoped recall, legacy DB migration, index rebuild,
  and platform backfill.

### Changed

- Gateway classification no longer relies on the platform allowlist alone: any
  request carrying an identity (or a non-`cli` platform) is treated as a gateway
  user and isolated per principal. Arbitrary platform values (e.g.
  `wechat_miniprogram`) are now isolated correctly instead of falling into the
  shared pool. The `gateway_platforms` allowlist is retained for compatibility.
- `principal_id` still isolates by user (email/id), so a user's memory is
  unified across platforms by default. Gateway requests with no identifiable
  user are classified into shared memory (`__shared__`).
- Bumped `EMBEDDER_VERSION` to `blake2b-counts-v2` to trigger a one-time
  semantic index rebuild for the new schema.

### Migration (0.2.x → 0.3.0)

- No manual script required. On the next provider `initialize()` the
  `memories.platform` column and index are added to existing databases and the
  semantic index is rebuilt automatically.
- Optionally run `backfill-platform` to recover real platform values for legacy
  rows. Rows whose provenance also lacks a platform are reported as
  `remaining_empty`.
- Memory already written to `__shared__` is not moved automatically; gateway
  history with no identifiable user remains shared by design.

### Verified

- `ruff check` and `ruff format`
- `pytest -q` (80 passed)

## 0.2.0 - 2026-05-28

### Added

- Added OpenSpec change `add-daily-memory-maintenance` for externally triggered daily user memory maintenance.
- Added `maintenance_service.py` with per-user `compact_user_day` and batch `compact_daily` operations.
- Added idempotent maintenance state tracking keyed by operation, profile, workspace, principal, and date.
- Added CLI commands:
  - `compact-user`
  - `compact-daily`
- Added maintenance policy support for `agent_context="maintenance"` same-principal `semantic_user` writes.
- Added tests for per-user maintenance isolation, idempotency, retry behavior, maintenance policy, and CLI argument paths.

### Changed

- Updated README and docs to describe external scheduling, Gateway identity requirements, and shared-memory maintenance separation.
- Updated provider `sync_turn` behavior so explicit non-current session writes remain episodic and do not promote durable memory before session switch.

### Verified

- `pytest -q`
- `python -m py_compile plugins/memory/layered_lancedb_sqlite/*.py tests/*.py`
- `openspec status --change add-daily-memory-maintenance`

## 0.1.0 - 2026-05-28

### Added

- Initial layered memory provider with SQLite canonical storage and LanceDB-compatible semantic indexing.
- Gateway user memory isolation and workspace shared memory support.
- OpenSpec-driven architecture refactor with centralized policy decisions and thinner provider orchestration.
