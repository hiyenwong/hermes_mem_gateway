# Changelog

All notable changes to this project are documented in this file.

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
