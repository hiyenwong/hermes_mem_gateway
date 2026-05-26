## 1. Provider Scaffold

- [x] 1.1 Create the Hermes memory provider plugin directory structure, entry point, manifest, and README scaffolding
- [x] 1.2 Define provider configuration schema, profile-scoped storage paths, and local config persistence rules
- [x] 1.3 Add dependency and environment setup for SQLite persistence and LanceDB indexing

## 2. Durable Storage Layer

- [x] 2.1 Implement SQLite schema creation for memory records, provenance, supersession, and lifecycle metadata
- [x] 2.2 Implement LanceDB index bootstrap and memory ID mapping back to SQLite canonical records
- [x] 2.3 Add storage validation and index rebuild support so LanceDB can be repaired from SQLite data

## 3. Namespace Routing

- [x] 3.1 Implement runtime namespace context resolution from workspace, platform, agent context, gateway `user_id`, and `session_id`
- [x] 3.2 Implement stable principal handling so gateway user semantic memory uses durable identity and unsafe identity sources do not
- [x] 3.3 Implement session-switch handling that rotates active session state and prevents writes into stale session namespaces

## 4. Recall and Write Lifecycle

- [x] 4.1 Implement `initialize()` and `prefetch()` to load provider state and assemble layered recall from episodic, user semantic, and shared semantic scopes
- [x] 4.2 Implement non-blocking `sync_turn()` that writes episodic records immediately and schedules deferred consolidation work
- [x] 4.3 Implement `queue_prefetch()`, `on_session_end()`, and `shutdown()` behavior for background recall, best-effort session extraction, and clean flush

## 5. Memory Governance

- [x] 5.1 Implement candidate classification rules that keep transient content episodic and promote stable high-value content conservatively
- [x] 5.2 Implement durable promotion into user semantic and shared semantic layers with provenance capture and builtin memory mirroring
- [x] 5.3 Implement reinforcement, decay, archival, and supersession rules so stale or replaced memory stops dominating recall

## 6. Verification

- [x] 6.1 Add tests for gateway versus non-gateway namespace routing, including missing-identity safety behavior
- [x] 6.2 Add tests for layered recall, session switching, and non-primary context write restrictions
- [x] 6.3 Add tests or fixtures for SQLite durability, LanceDB rebuild flow, and conservative promotion or supersession behavior
