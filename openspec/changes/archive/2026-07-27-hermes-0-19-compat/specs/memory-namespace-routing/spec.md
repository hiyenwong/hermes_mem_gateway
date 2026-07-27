## MODIFIED Requirements

### Requirement: Provider SHALL update active namespace on session switches
The system SHALL recompute active session-aware routing state when Hermes changes session identity mid-process. When the host defers session-end extraction and switch notification to an asynchronous boundary task (as of Hermes 0.19's `commit_session_boundary_async`), episodic scope resolution SHALL still follow the session id supplied on each call rather than waiting for that boundary task to complete.

#### Scenario: Resume or branch changes active session
- **WHEN** Hermes notifies the provider of `on_session_switch`
- **THEN** subsequent reads and writes use the new session identity and no longer target the previous session namespace

#### Scenario: Reset starts a new logical conversation
- **WHEN** Hermes signals a reset-style session switch
- **THEN** the provider clears or rotates any session-scoped buffers so new episodic writes do not attach to the previous conversation

#### Scenario: Prefetch called during the deferred session-boundary window
- **WHEN** the host calls `prefetch()` with a new session id after `/new` returns but before its queued session-boundary task (`on_session_end` + `on_session_switch(reset=True)`) has executed
- **THEN** the provider resolves episodic scope using the supplied new session id, so no episodic content from the previous session leaks into the new session's recall, even though workspace/user runtime fields have not yet rebound
