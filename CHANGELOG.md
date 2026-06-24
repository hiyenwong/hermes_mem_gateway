# Changelog

All notable changes to this project are documented in this file.

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
