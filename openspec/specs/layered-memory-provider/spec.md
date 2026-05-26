# layered-memory-provider Specification

## Purpose
TBD - created by archiving change add-layered-lancedb-sqlite-memory-provider. Update Purpose after archive.
## Requirements
### Requirement: Provider SHALL persist memory with hybrid durable and semantic storage
The system SHALL provide a Hermes external memory provider that stores canonical memory records and lifecycle metadata in SQLite, while using LanceDB only for semantic retrieval indexing of eligible records.

#### Scenario: Provider initializes local storage
- **WHEN** the provider is initialized for a Hermes profile
- **THEN** it creates or validates profile-scoped SQLite storage and LanceDB index locations under the active Hermes home

#### Scenario: Durable memory survives retrieval index failure
- **WHEN** LanceDB indexing is unavailable or corrupted
- **THEN** SQLite remains the authoritative memory store and the provider can rebuild semantic indexes from canonical records

### Requirement: Provider SHALL separate episodic and semantic memory layers
The system SHALL store session-bound episodic memory separately from durable semantic memory so temporary conversation state does not automatically become long-term recall.

#### Scenario: Turn data enters episodic storage first
- **WHEN** a user turn and assistant response are synchronized
- **THEN** the provider records them as session-scoped episodic memory before any semantic promotion occurs

#### Scenario: Durable semantic recall excludes unpromoted episodic content
- **WHEN** the provider assembles long-term memory recall
- **THEN** it excludes episodic-only records that have not been promoted into semantic layers

### Requirement: Provider SHALL support user and shared semantic layers
The system SHALL maintain separate durable semantic layers for gateway user memory and workspace shared memory.

#### Scenario: Gateway user memory is stored separately
- **WHEN** durable memory is promoted from a gateway conversation with a stable user identity
- **THEN** the provider stores the durable record in a user-scoped semantic layer tied to that identity

#### Scenario: Non-gateway durable memory is shared
- **WHEN** durable memory is promoted from a non-gateway primary conversation
- **THEN** the provider stores the durable record in the workspace shared semantic layer

### Requirement: Provider SHALL keep post-turn synchronization non-blocking
The system SHALL ensure that Hermes post-turn synchronization remains non-blocking even when memory extraction, embedding, or indexing work is required.

#### Scenario: Turn synchronization schedules deferred work
- **WHEN** a completed turn must be consolidated or indexed
- **THEN** the provider persists or enqueues the minimum durable turn record immediately and performs heavier work asynchronously

#### Scenario: Session-end extraction is not required for correctness
- **WHEN** a gateway session ends without a reliable session-end callback
- **THEN** the durable turn history already stored by the provider remains sufficient to preserve memory correctness

### Requirement: Provider SHALL inject minimal gateway user context into prompts without exposing raw headers
The system SHALL inject a minimal gateway user context block for OpenWebUI-derived requests that communicates user display context and privacy scope without exposing raw transport headers.

#### Scenario: Prompt includes private gateway scope
- **WHEN** the provider assembles prompt context for an identified gateway user
- **THEN** it includes minimal user display and privacy-scope context that indicates the request is private by default

#### Scenario: Prompt does not expose raw headers
- **WHEN** the provider injects gateway user context into prompts
- **THEN** it does not include raw `X-OpenWebUI-User-*` headers verbatim

### Requirement: Provider SHALL record attribution and shared-authorization provenance for gateway writes
The system SHALL persist provenance metadata describing how gateway identity and shared-write policy were resolved for memory writes.

#### Scenario: Private gateway write records principal source
- **WHEN** a gateway request writes private memory
- **THEN** the provider records provenance describing the resolved principal source and gateway policy context

#### Scenario: Shared gateway write records authorization path
- **WHEN** a gateway request writes shared memory through an allowlisted and explicit path
- **THEN** the provider records provenance showing that shared intent and shared authorization both succeeded

