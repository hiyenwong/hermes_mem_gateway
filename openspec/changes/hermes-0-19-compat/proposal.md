## Why

Hermes Agent has moved from 0.18.0 to 0.19.0. The `MemoryProvider` abstract
base class is unchanged, so the plugin loads and runs without modification —
but `MemoryManager` (the host component that drives the provider) changed how
it sequences the `/new` session boundary and how it drains background work at
shutdown. Both changes interact with assumptions this provider's 0.18
adaptation (`commit 3226815`) baked in. Verifying and tightening those
assumptions now avoids a silent correctness or data-loss gap once the host is
upgraded.

## What Changes

- Add a test that pins the fail-safe behavior of `prefetch()` when it is
  called with a new session's ID during the window between `/new` returning
  and the host's now-asynchronous `commit_session_boundary_async` task
  landing (episodic scope must follow the new session id even though
  workspace/user runtime fields have not yet rebound).
- Lower the provider's internal `_background.drain(timeout=...)` budget used
  in `on_session_switch` and `shutdown()` so the combined provider-side drain
  path stays safely under the host's 5s shutdown drain window, and add a test
  asserting `shutdown()` completes within that bound.
- Add `version` to `plugin.yaml`, kept in sync with `pyproject.toml`, so the
  0.19 desktop plugins panel can display it.
- Update `README.md` to state compatibility across Hermes 0.18–0.19 instead
  of 0.18 only, and note the host's prefetch timeout is now a fixed 8s
  constant (no longer configurable via
  `HERMES_EXTERNAL_MEMORY_PREFETCH_TIMEOUT`), which does not require gateway
  changes but is relevant to operators tuning cold-start LanceDB index
  rebuilds.
- Bump version per `CLAUDE.md`'s SemVer policy and update `CHANGELOG.md`.

Out of scope: adopting the new declarative `config_schema.py` desktop
config-panel mechanism (0.19 keeps the legacy `get_config_schema()` /
`save_config()` instance path fully supported; this is a separate,
non-urgent enhancement).

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `memory-namespace-routing`: clarify the session-switch requirement to
  cover the async boundary window introduced by the host's
  `commit_session_boundary_async` — episodic scope must follow the new
  session id immediately, even before the provider's own rebinding of
  workspace/user runtime fields completes.
- `layered-memory-provider`: tighten the non-blocking-sync requirement to
  state that provider-side shutdown draining must complete within the host's
  shutdown drain budget, not just "eventually."

## Impact

- Affected code: `plugins/memory/layered_lancedb_sqlite/__init__.py`
  (drain timeout constants), `plugin.yaml`, `README.md`,
  `tests/test_provider.py` (new tests).
- Affected specs: `memory-namespace-routing`, `layered-memory-provider`.
- No storage schema, isolation semantics, or public interface changes —
  drop-in upgrade, PATCH-level version bump.
