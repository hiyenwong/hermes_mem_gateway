## MODIFIED Requirements

### Requirement: Provider SHALL keep post-turn synchronization non-blocking
The system SHALL schedule expensive memory synchronization work off the request-completion path so end-user latency is not affected by durable storage operations. Provider-side draining of that deferred work during session switches and shutdown SHALL complete within the host's shutdown drain budget (Hermes 0.19's `MemoryManager` bounds this to 5 seconds), so in-flight writes are not misreported as abandoned when they would otherwise have completed.

#### Scenario: Turn synchronization schedules deferred work
- **WHEN** a turn completes
- **THEN** the provider enqueues heavier synchronization work rather than performing it inline on the response path

#### Scenario: Session-end extraction is not required for correctness
- **WHEN** session-end extraction has not yet run
- **THEN** durable memory correctness for already-synced turns is unaffected

#### Scenario: Provider drains within the host's shutdown budget
- **WHEN** the host tears down the provider via `on_session_switch` followed by `shutdown()` in the same session-boundary sequence
- **THEN** the provider's combined internal drain wait completes with headroom under the host's 5-second shutdown drain budget, so outstanding writes are not falsely reported as abandoned
