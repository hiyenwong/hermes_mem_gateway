## 1. Maintenance Storage And State

- [x] 1.1 Add storage helpers to enumerate user principals by profile and workspace from canonical SQLite records.
- [x] 1.2 Add maintenance state helpers keyed by operation kind, profile, workspace, principal, and date.
- [x] 1.3 Add idempotency checks so completed maintenance keys do not create duplicate output.
- [x] 1.4 Add retry behavior so failed maintenance keys can be re-run and marked completed.

## 2. Maintenance Policy And Namespace

- [x] 2.1 Add policy support for `agent_context="maintenance"` same-principal `semantic_user` writes.
- [x] 2.2 Block maintenance writes to different user principals.
- [x] 2.3 Block per-user maintenance writes to `semantic_shared` unless a separate shared maintenance operation is explicitly invoked.
- [x] 2.4 Add namespace construction helpers for maintenance jobs using Gateway email or user ID.
- [x] 2.5 Reject display-name-only maintenance identities.

## 3. Maintenance Service

- [x] 3.1 Add `maintenance_service.py` with `compact_user_day` and `compact_daily` service functions.
- [x] 3.2 Ensure `compact_user_day` queries only the resolved profile, workspace, principal, and date scope.
- [x] 3.3 Ensure compaction output writes to the same user's `semantic_user` scope with maintenance provenance.
- [x] 3.4 Ensure archival or supersession updates record maintenance reason metadata.
- [x] 3.5 Keep deterministic compaction behavior independent of any required LLM summarizer.

## 4. CLI Integration

- [x] 4.1 Add `compact-user` CLI command with profile, workspace, date, and Gateway identity arguments.
- [x] 4.2 Add `compact-daily` CLI command with profile, workspace, and date arguments.
- [x] 4.3 Add maintenance status output that reports completed, failed, skipped, and processed counts.
- [x] 4.4 Keep existing validate and rebuild-index commands stable.

## 5. Tests And Documentation

- [x] 5.1 Add tests for per-user principal isolation during compaction.
- [x] 5.2 Add tests for maintenance idempotency and failed-job retry.
- [x] 5.3 Add policy tests for maintenance same-principal, cross-principal, and shared-default-denied paths.
- [x] 5.4 Add CLI tests for compact-user and compact-daily argument handling.
- [x] 5.5 Update README and docs to explain external scheduling, Gateway identity requirements, and shared-maintenance separation.
- [x] 5.6 Run the full test suite and `openspec status --change add-daily-memory-maintenance`.
