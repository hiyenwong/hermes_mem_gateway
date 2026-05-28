## Why

User memory will accumulate across Gateway sessions and needs periodic consolidation, deduplication, and archival without mixing users or relying on normal chat turns. Daily maintenance should be triggered by Hermes or an external scheduler while still using Gateway identity context so every user's memory remains isolated by principal.

## What Changes

- Add a daily memory maintenance capability exposed by the provider as explicit service/CLI operations, not as an internal timer.
- Add per-user compaction that runs with Gateway-derived identity context and writes results only to the same user's `semantic_user` scope.
- Add daily maintenance state tracking so jobs are idempotent, resumable, and auditable per profile/workspace/principal/date.
- Add a way to enumerate user principals eligible for maintenance from canonical SQLite records.
- Add policy support for a `maintenance` execution context that may write same-principal user maintenance output but does not write shared memory by default.
- Keep shared memory maintenance separate from per-user maintenance.

## Capabilities

### New Capabilities

- `daily-memory-maintenance`: Daily user memory compaction, idempotent maintenance state tracking, and CLI/service entry points for Hermes-triggered maintenance.

### Modified Capabilities

- `memory-namespace-routing`: define how maintenance jobs use Gateway identity fields to resolve isolated per-user namespaces.
- `memory-lifecycle-governance`: define maintenance-context durable write policy, provenance, idempotency, and shared-memory boundaries.

## Impact

- Affected code: provider CLI, storage queries, maintenance state handling, policy decisions, and tests.
- Affected docs: README and architecture docs should describe external scheduling and per-user isolation.
- APIs: add provider maintenance/CLI entry points; existing chat hooks remain stable.
- Storage: reuse SQLite canonical records and `maintenance_state`; no LanceDB schema change expected.
- Dependencies: no new runtime dependency is expected.
