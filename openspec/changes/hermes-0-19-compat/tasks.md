## 1. Session-boundary window behavior (memory-namespace-routing)

- [x] 1.1 In `tests/test_provider.py`, add a test that calls `prefetch()` (or `sync_turn()`) with a new session id immediately after simulating a pending `/new` boundary — i.e. before `on_session_switch(new_id, reset=True, ...)` has been invoked on the provider — and asserts the resulting namespace/cache key targets the new session id for episodic scope.
- [x] 1.2 Assert in the same test that no cached recall entry keyed to the previous session leaks into the result returned for the new session id.
- [x] 1.3 Confirm (via code reading, not a behavior change) that `_active_namespace(session_id=...)` in `plugins/memory/layered_lancedb_sqlite/__init__.py` already threads the explicit `session_id` through for both `prefetch` and `sync_turn`; no production code change is required for this section, only the test.

## 2. Bounded shutdown drain (layered-memory-provider)

- [x] 2.1 In `plugins/memory/layered_lancedb_sqlite/__init__.py`, lower the `timeout` argument passed to `self._background.drain(...)` in `on_session_switch` from 5 to 3 seconds.
- [x] 2.2 Lower the `timeout` argument passed to `self._background.drain(...)` in `shutdown()` from 5 to 3 seconds.
- [x] 2.3 Add a test in `tests/test_provider.py` that calls `on_session_switch(...)` followed by `shutdown()` in sequence (mirroring a host teardown after `/new`) and asserts the combined elapsed wall-clock time stays under the host's 5-second shutdown drain budget.
- [x] 2.4 Add a test asserting `shutdown()` still fully drains and closes the store under normal (non-timeout) conditions, so the timeout reduction does not silently drop pending writes in the common case.

## 3. Documentation and metadata

- [x] 3.1 Add a `version:` field to `plugin.yaml`, set to match the new `pyproject.toml` version from task 4.1.
- [x] 3.2 Update `README.md` compatibility statement from "Hermes 0.18" to "Hermes 0.18-0.19".
- [x] 3.3 Add a short `README.md` note that the host's external-provider prefetch timeout is a fixed 8s constant as of Hermes 0.19 (previously configurable via `HERMES_EXTERNAL_MEMORY_PREFETCH_TIMEOUT`, which this provider never read), relevant to operators relying on cold-start LanceDB index rebuilds completing within a prefetch call.

## 4. Versioning and release hygiene

- [x] 4.1 Bump `version` in `pyproject.toml` from `0.6.0` to `0.6.1` (PATCH: backward-compatible fix/verification, no schema or interface change).
- [x] 4.2 Add a new `CHANGELOG.md` entry at the top for `0.6.1` under `Fixed`, describing the drain-timeout tightening and the session-boundary-window test coverage.
- [x] 4.3 Update `CLAUDE.md`'s "当前版本" to `0.6.1`.

## 5. Verification

- [x] 5.1 Run `ruff check --fix` and `ruff format`.
- [x] 5.2 Run `pytest tests/` and confirm all tests pass, including the new tests from sections 1 and 2.
- [x] 5.3 Confirm the three version references (`pyproject.toml`, `CHANGELOG.md`, `CLAUDE.md`) are consistent per `CLAUDE.md`'s policy.
