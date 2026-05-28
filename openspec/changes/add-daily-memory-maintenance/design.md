## Context

The provider already stores Gateway user memory under stable per-user principals and uses SQLite as the canonical store. As memory accumulates, Hermes needs a way to compact, deduplicate, summarize, archive, or repair user memory on a daily cadence without mixing users.

The maintenance trigger should not be an in-process timer owned by the provider. Hermes, cron, systemd, Kubernetes CronJob, or another scheduler should trigger explicit provider maintenance commands. The provider should own the maintenance service, policy checks, storage queries, and idempotent maintenance state.

## Goals / Non-Goals

**Goals:**

- Add a `maintenance_service.py` that performs per-user daily maintenance using canonical SQLite records.
- Add CLI operations for `compact-user`, `compact-daily`, and maintenance validation/status.
- Ensure each user compaction runs with Gateway-derived identity context and only reads/writes that user's principal scope.
- Record per-profile/workspace/principal/date maintenance state for idempotency and retry safety.
- Allow a dedicated `agent_context="maintenance"` policy path for same-principal user memory maintenance.
- Keep shared memory maintenance separate from per-user maintenance.

**Non-Goals:**

- Adding an internal scheduler or long-running daemon to the provider.
- Adding LLM summarization as a hard dependency in this change.
- Changing existing chat hook behavior.
- Changing the SQLite memory record schema unless a small maintenance-state extension is required.
- Compacting `semantic_shared` as part of per-user daily compaction.

## Decisions

### Decision: External scheduling, provider-owned operation

Hermes or an external scheduler will call explicit CLI/service entry points. The provider will not run its own daily timer.

Rationale: external scheduling handles uptime, retries, deployment topology, and observability better than a plugin lifecycle hook. Provider-owned commands still keep storage and namespace behavior close to the memory implementation.

Alternative considered: run a timer inside `initialize`. This is fragile when Hermes has multiple processes, restarts, or inactive plugin instances.

### Decision: Maintenance uses Gateway identity context

Per-user maintenance will construct a namespace using the same identity fields as Gateway traffic: `platform="gateway"`, `agent_context="maintenance"`, `user_email` or `user_id`, `agent_workspace`, and `agent_identity`.

Rationale: compaction should use the same principal resolution model as normal Gateway memory. This keeps user isolation consistent and testable.

Alternative considered: scan all users and pass raw `principal_id` strings directly to storage. This is simpler but bypasses the identity model and increases cross-user write risk.

### Decision: Same-principal writes only

Maintenance policy may write `semantic_user` records only for the namespace principal being compacted. It must not default to `semantic_shared`; shared maintenance will be a separate operation with separate authorization.

Rationale: daily user compaction is a privacy-sensitive batch job. Its safest default is same-principal read and same-principal write.

Alternative considered: allow user compaction to also update shared facts. That mixes personal and shared scopes and should require a distinct review path.

### Decision: Idempotent maintenance state keys

Maintenance state will be keyed by profile, workspace, principal, date, and operation kind, for example:

`daily_compaction:{profile}:{workspace}:{principal}:{date}`

State values should capture `started`, `completed`, `failed`, processed counts, output IDs, and error summaries.

Rationale: daily jobs must be safe to retry after partial failures and must avoid duplicate summaries or duplicate archival.

Alternative considered: rely only on output fingerprints. Fingerprints help but do not explain failed or partially completed runs.

### Decision: Start with deterministic compaction primitives

The first implementation should support deterministic cleanup primitives such as duplicate reinforcement, stale episodic summarization placeholders, superseded record archival, and maintenance provenance. If LLM summarization is later added, it should plug into the maintenance service behind an optional summarizer interface.

Rationale: deterministic behavior is easier to verify and safe to run in batch. LLM summarization can be added after namespace and idempotency boundaries are proven.

Alternative considered: make LLM summarization the core feature immediately. That increases dependency, privacy, and verification complexity.

## Risks / Trade-offs

- Cross-user contamination risk -> require namespace-aware storage queries with `profile_id`, `workspace_id`, and exact `principal_id` in every user maintenance read/write.
- Duplicate compaction output -> use deterministic maintenance keys and output fingerprints.
- Long-running daily jobs -> provide per-user CLI and daily batch CLI so failed users can be retried individually.
- Maintenance writes bypassing normal policy -> add explicit `maintenance` context decisions and table-driven policy tests.
- Shared memory pollution -> keep shared maintenance as a separate command and block shared writes from per-user daily compaction.

## Migration Plan

1. Add maintenance service and storage helpers for principal enumeration and maintenance state.
2. Add policy support for `agent_context="maintenance"` same-principal writes.
3. Add CLI entry points for `compact-user` and `compact-daily`.
4. Add tests for namespace isolation, idempotency, per-user retry, and shared write blocking.
5. Update README and docs to explain external scheduling and Gateway identity requirements.

Rollback strategy: maintenance commands are additive. If issues appear, disable scheduled invocation and leave existing chat-time provider behavior unchanged.

## Open Questions

- Which upstream Gateway user source should Hermes use for the authoritative daily user list: Gateway user table, recent activity, or memory DB principal enumeration?
- Should failed maintenance state store full error text or only sanitized summaries?
- Should compaction output be a new semantic record kind such as `daily_compaction_summary`, or reuse `builtin_memory` with metadata?
