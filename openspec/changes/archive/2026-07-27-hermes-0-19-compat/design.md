## Context

Hermes Agent 0.19.0 (`3ef6bbd2`) changed `agent/memory_manager.py` relative
to 0.18.0 (`7c1a0295`) in four ways; `agent/memory_provider.py` (the ABC this
plugin implements) did not change:

1. `/new` no longer calls `on_session_end` + `on_session_switch(reset=True)`
   inline. `MemoryManager.commit_session_boundary_async()` bundles both into
   one task on the manager's single background worker, FIFO-ordered against
   per-turn `sync_turn` calls. This preserves end→switch ordering and
   non-blocking `/new`, but means there is now a window — between `/new`
   returning and that task executing — where the host may call `prefetch()`
   with the **new** session id while this provider's `_runtime` (workspace,
   user identity) still reflects the **old** session.
2. External prefetch timeout is now a fixed `_EXTERNAL_PREFETCH_TIMEOUT_S =
   8.0` constant (constructor-overridable only); the
   `HERMES_EXTERNAL_MEMORY_PREFETCH_TIMEOUT` env var this provider never read
   is gone. No provider change needed, but cold-start LanceDB index rebuild
   time is now bounded by a value the operator can no longer tune via env.
3. Shutdown draining is now bounded: `_SYNC_DRAIN_TIMEOUT_S = 5.0`, after
   which the manager stops waiting, rejects further submissions, and reports
   abandoned write/prefetch counts. This provider's `on_session_switch` calls
   `self._background.drain(timeout=5)` and `shutdown()` calls
   `self._background.drain(timeout=5)` again — if both fire in the same
   shutdown sequence, the combined wait can exceed the host's 5s budget,
   causing in-flight provider writes to be reported as abandoned even though
   they would have completed.
4. Provider-exposed tools now respect disabled toolsets. This provider
   returns no runtime tools (`get_tool_schemas()` is empty,
   `handle_tool_call()` raises), so this is a no-op for us.

This design covers items 1 and 3, which require code and spec changes. Item 2
is a documentation note. Item 4 needs no action.

## Goals / Non-Goals

**Goals:**
- Make the `prefetch()` behavior during the `/new` async boundary window an
  explicit, tested contract rather than an accident of current field
  ordering.
- Ensure the provider's own drain budget never causes the host to see
  writes as abandoned when they would otherwise complete inside the host's
  5s window.
- Keep the provider version/docs accurate for host 0.18–0.19 compatibility.

**Non-Goals:**
- Adopting the 0.19 declarative `config_schema.py` desktop config-panel
  mechanism — the legacy instance `get_config_schema()`/`save_config()` path
  is fully supported by 0.19's dispatch logic, so this is a separate,
  lower-priority enhancement.
- Changing storage schema, namespace resolution logic, or promotion policy.
- Adding a provider-side mutex or synchronization primitive to eliminate the
  boundary window outright — the host's own serialization (FIFO worker) is
  the correctness mechanism; the provider only needs to behave safely while
  the window is open, not close it.

## Decisions

### D1: Treat the `/new` boundary window as fail-safe-by-scope, not fail-closed

**Decision**: Keep `prefetch()`/`sync_turn()` using the caller-supplied
`session_id` for episodic scope (as they already do — `_active_namespace`
takes `session_id` as an explicit override), and do not add provider-side
blocking/locking to wait for the pending `commit_session_boundary_async`
task. Document and test that during the window, episodic reads/writes
correctly target the new session while workspace/user scope may briefly lag
by one boundary task.

**Rationale**: The host's own FIFO worker is what guarantees ordering
correctness for on_session_end/on_session_switch relative to sync_turn; nothing
in the provider needs to duplicate that guarantee. Since `session_id` is
threaded per-call already (not solely read from `self._namespace`), episodic
isolation — the property that matters for correctness (no cross-session
leakage) — already holds. The workspace/user lag is bounded by one queued
task and self-heals as soon as the boundary task runs; blocking `prefetch()`
to wait for it would reintroduce the inline-blocking problem 0.19 was
designed to remove upstream.

**Alternatives considered**:
- *Block `prefetch()` until pending boundary tasks drain*: rejected — turns a
  host-side non-blocking redesign into a provider-side blocking call,
  defeating its purpose, for a lag that is already scoped safely.
- *Add a provider-side session generation counter to reject stale reads*:
  rejected as over-engineering for a bounded, self-correcting window with no
  observed correctness impact — revisit only if real cross-session leakage is
  found.

### D2: Lower provider-side drain timeouts to fit inside the host's shutdown budget

**Decision**: Reduce the `timeout` passed to `self._background.drain(...)` in
both `on_session_switch` and `shutdown()` from 5s to a smaller value (3s),
and add a test asserting `shutdown()` (which may call drain twice across a
switch-then-shutdown sequence) completes within the host's 5s budget in the
common case.

**Rationale**: The host's `_SYNC_DRAIN_TIMEOUT_S` is a hard ceiling on how
long it will wait during teardown before marking outstanding work abandoned.
This provider's own drain calls are nested inside that window (they run
inside the host's per-provider `shutdown()`/`on_session_switch()` dispatch),
so a provider-side 5s drain can itself consume the entire host budget before
the host's own bookkeeping completes, turning what should be a completed
write into a reported abandonment. Trimming to 3s leaves headroom.

**Alternatives considered**:
- *Leave at 5s*: rejected — directly risks false-abandoned reporting under
  the host's new accounting.
- *Make timeout configurable via config.yaml*: rejected as unnecessary
  complexity for a fixed internal safety margin; revisit only if operators
  report drain timeouts under real load.

## Risks / Trade-offs

- [Risk] Lowering the drain timeout to 3s could abandon slow local writes
  (e.g. large LanceDB index updates) that would have completed in 4-5s. →
  Mitigation: `_background.drain()` already logs when it times out; this is
  the same trade-off the host itself made in choosing 5s over a longer value,
  just applied more conservatively at our layer. No data is lost — undrained
  work is queued, not cancelled — only the "waited for completion" guarantee
  becomes tighter.
- [Risk] A test asserting exact prefetch behavior during the async boundary
  window is inherently timing-sensitive. → Mitigation: use the provider's
  existing pattern of calling `on_session_switch(new_id, ...)` and
  `prefetch()` directly in test code rather than a real background sleep,
  asserting on namespace/cache-key composition rather than wall-clock races
  (mirrors the existing `test_provider.py` tests added in commit 3226815).

## Migration Plan

Drop-in PATCH upgrade: no config, schema, or index changes. Steps: implement
tasks, run `ruff check --fix && ruff format && pytest tests/`, bump version
per `CLAUDE.md`, update `CHANGELOG.md`, commit. No rollback concerns beyond a
normal git revert — behavior changes are additive/tightening, not schema or
API breaking.

## Open Questions

- None blocking. If a future host upgrade adds a hook to explicitly signal
  "boundary task complete," we should switch D1's window-tolerant approach to
  an event-driven one instead of relying on bounded self-correction.
