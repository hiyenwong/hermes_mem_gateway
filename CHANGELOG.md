# Changelog

All notable changes to this project are documented in this file.

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
