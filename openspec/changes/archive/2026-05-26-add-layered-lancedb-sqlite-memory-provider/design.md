## Context

This change introduces a new Hermes external memory provider for a project that currently has no local implementation code but has clear architectural requirements. The provider must work within Hermes's memory provider lifecycle, respect profile-scoped storage under `hermes_home`, and remain safe under gateway-specific behavior where runtime context can vary by user, session, and agent execution mode.

The main design pressure comes from three conflicting needs:

- Gateway users need isolated long-term memory so one user's preferences and history do not leak into another user's recall.
- Sessions need isolated episodic memory so temporary context can help current conversations without polluting durable knowledge.
- Non-gateway usage still needs shared recall so a single local operator can build a common memory corpus within a configured workspace.

Hermes already provides lifecycle hooks for initialization, prefetch, post-turn synchronization, session switching, session-end extraction, and builtin memory write mirroring. Upstream documentation and issues show two operational constraints that shape this design:

- `sync_turn()` must be non-blocking and cannot rely on session-end hooks for durable writes.
- Session identity can change mid-process, and gateway behavior has historically exposed edge cases around `on_session_end()` and session-scoped provider state.

The provider therefore needs a conservative architecture that treats SQLite as the durable source of truth and LanceDB as an auxiliary retrieval index.

## Goals / Non-Goals

**Goals:**

- Provide a Hermes-compatible memory provider with hybrid SQLite plus LanceDB storage.
- Separate memory into session episodic, gateway user semantic, and workspace shared semantic layers.
- Resolve read and write scope from configured workspace, runtime `user_id`, `session_id`, and agent execution context.
- Support asynchronous consolidation from raw episodic events into semantic memory.
- Support basic memory governance with provenance, decay, reinforcement, and supersession metadata.
- Keep provider behavior safe for non-primary contexts such as subagents, cron jobs, and flush helpers.

**Non-Goals:**

- Reproduce the full ZenBrain research architecture, including predictive memory, neuromodulator simulation, or sleep-style batch replay.
- Replace Hermes builtin `MEMORY.md` and `USER.md` files.
- Depend on `on_session_end()` as the only or primary persistence path.
- Implement cross-workspace memory sharing or automatic tenant federation.
- Build a graph-memory or agent-procedural skill system in the first iteration.

## Decisions

### 1. Use SQLite as the source of truth and LanceDB as a retrieval accelerator

The provider will store canonical memory rows, lifecycle metadata, provenance, and namespace fields in SQLite. LanceDB will index only eligible textual recall units and will reference SQLite memory IDs rather than owning the authoritative record.

Rationale:

- SQLite is better suited for exact namespace filtering, auditability, version chains, and migration-safe updates.
- LanceDB is better suited for semantic retrieval but is awkward as a truth store when records must be superseded, archived, or reclassified.
- This split supports future recall tuning without rewriting durability logic.

Alternatives considered:

- LanceDB-only storage was rejected because it makes governance, migration, and exact-scope filtering harder.
- SQLite-only storage was rejected because semantic retrieval quality and speed would be worse for long-lived memory corpora.

### 2. Represent memory as layers rather than a flat corpus

The provider will define three runtime memory layers:

- `episodic`: session-scoped, temporary, conversation-bound memory
- `semantic_user`: gateway user-scoped durable memory
- `semantic_shared`: workspace-scoped durable memory

Metadata and governance state will live alongside these layers rather than as a fourth user-visible recall layer.

Rationale:

- Layered recall allows temporary context to remain useful without contaminating long-term memory.
- Gateway and non-gateway usage need different durable scopes.
- Layer-aware retrieval prevents high-frequency shared project facts from overwhelming user-specific recall.

Alternatives considered:

- A single semantic layer with metadata filters was rejected because it blurs lifecycle boundaries and makes consolidation policy brittle.
- A larger seven-layer model was rejected for the initial implementation because it adds complexity before the core isolation model is proven.

### 3. Resolve durable scope from namespace context

Each memory record will carry namespace dimensions:

- `profile_id`
- `workspace_id`
- `principal_id`
- `session_id` when applicable
- `layer`
- `kind`

The provider will derive `principal_id` as follows:

- Gateway primary context with stable `user_id`: use `user_id`
- Non-gateway contexts: use `__shared__`
- Missing gateway identity: fall back to a configured safe resolver or reject promotion to user semantic memory

Rationale:

- Workspace, identity, and session are different boundaries and need to remain independently queryable.
- Stable identity is required for gateway isolation; usernames or display names are not sufficient.

Alternatives considered:

- Collapsing all scope into a single composite key was rejected because it hides important distinctions and makes policy checks harder.

### 4. Make `sync_turn()` the reliable write path and `on_session_end()` a best-effort enhancer

At turn completion, the provider will synchronously enqueue or persist an episodic event record and schedule asynchronous consolidation work. Session-end hooks may produce summaries or final extraction passes, but correctness must not depend on them.

Rationale:

- Hermes explicitly requires `sync_turn()` to remain non-blocking.
- Upstream gateway behavior has had gaps around session-end notifications.
- Durable turn capture is more reliable than end-of-session extraction.

Alternatives considered:

- Session-end-only extraction was rejected because it risks silent memory loss.

### 5. Restrict long-term writes in non-primary agent contexts

The provider will default to allowing durable writes only from `agent_context == "primary"`. Subagents, cron jobs, and flush helpers may read scoped memory, but durable writes will be blocked or heavily restricted unless explicitly classified as safe summary material.

Rationale:

- Hermes documentation warns that non-primary contexts can distort user representations.
- This reduces accidental contamination from synthetic prompts and delegated tasks.

Alternatives considered:

- Allowing all contexts to write was rejected as too risky.

### 6. Use conservative consolidation and version-aware updates

Raw turns will first enter episodic storage. Promotion into semantic layers will require explicit memory signals, repeated evidence, or high-confidence stable facts. When new durable content conflicts with older content, the provider will create a new row and link it through `supersedes_id` rather than mutating history in place.

Rationale:

- Conservative promotion reduces pollution from transient or hallucinated content.
- Supersession preserves auditability and supports evolving user preferences and project facts.

Alternatives considered:

- Immediate promotion of all extracted facts was rejected because it would quickly degrade retrieval quality.
- In-place updates were rejected because they lose provenance and make conflict debugging harder.

## Risks / Trade-offs

- [Gateway identity may be absent or unstable on some platforms] -> Require a stable principal resolution policy and block user-semantic promotion when identity confidence is insufficient.
- [Shared workspace memory can become noisy over time] -> Apply conservative promotion thresholds, decay, archive policies, and layer-aware retrieval limits.
- [SQLite and LanceDB can drift if updates partially fail] -> Treat SQLite commits as authoritative and rebuild or repair LanceDB indexes from SQLite when needed.
- [Session switching may cause writes to land in the wrong scope] -> Recompute active namespace state on `on_session_switch()` and pass session-aware parameters through retrieval and sync paths.
- [Overly aggressive consolidation may turn temporary statements into durable facts] -> Start with explicit-memory and repeated-evidence rules; keep promotion thresholds configurable.
- [Too much policy complexity can slow initial delivery] -> Limit MVP behavior to three memory layers, simple scoring, and deterministic governance rules.

## Migration Plan

1. Add provider package structure, configuration schema, and storage bootstrap paths under profile-scoped Hermes home.
2. Implement SQLite schema creation and startup validation.
3. Implement LanceDB index creation and rebuild tooling tied to SQLite memory IDs.
4. Implement namespace context resolution and primary-context write policy checks.
5. Implement episodic turn capture in `sync_turn()` and basic session-aware recall in `prefetch()`.
6. Add asynchronous consolidation into user and shared semantic layers with supersession support.
7. Add mirroring from builtin memory writes and archive/repair CLI helpers if needed.
8. Validate behavior in gateway and non-gateway scenarios, including session switching and non-primary contexts.

Rollback strategy:

- Disable the provider in Hermes config to fall back to builtin memory only.
- Preserve SQLite records as the authoritative store even if LanceDB indexing is disabled or corrupted.
- Rebuild retrieval indexes from SQLite after rollback or partial deployment failures.

## Open Questions

- Should gateway group threads support an optional shared semantic layer distinct from workspace shared memory, or should shared memory remain workspace-wide only in the first release?
- What minimum confidence or evidence threshold should promote a record from episodic to semantic memory in MVP?
- Should provider configuration allow a custom principal resolver for platforms where Hermes runtime `user_id` is incomplete?
- How much session summary material should be retained after episodic decay: full per-turn rows, rolling summaries, or both?
