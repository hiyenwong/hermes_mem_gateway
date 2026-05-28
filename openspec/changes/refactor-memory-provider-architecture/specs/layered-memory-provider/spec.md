## ADDED Requirements

### Requirement: Provider implementation SHALL have one canonical editable source
The system SHALL maintain the layered memory provider implementation in a single canonical package path so runtime behavior, tests, and packaging cannot drift across duplicate module trees.

#### Scenario: Tests import canonical provider package
- **WHEN** the provider test suite imports the layered memory provider
- **THEN** it imports the implementation from `plugins.memory.layered_lancedb_sqlite`

#### Scenario: Duplicate root modules do not own behavior
- **WHEN** a root-level compatibility module exists for historical imports
- **THEN** it delegates to the canonical plugin package and does not contain independent provider, policy, namespace, governance, storage, or CLI logic

### Requirement: Provider class SHALL remain a thin Hermes adapter
The system SHALL keep Hermes-facing provider hooks stable while delegating recall, promotion, memory-write mirroring, prompt formatting, and background task handling to focused internal modules.

#### Scenario: Provider receives a Hermes recall hook
- **WHEN** Hermes calls the provider recall entry point
- **THEN** the provider resolves runtime context and delegates layered recall assembly to the recall service

#### Scenario: Provider receives a Hermes turn synchronization hook
- **WHEN** Hermes calls the provider turn synchronization entry point
- **THEN** the provider persists the required episodic record and delegates durable promotion work to the promotion service

#### Scenario: Provider shuts down
- **WHEN** Hermes shuts down the provider
- **THEN** the provider delegates pending task draining and error handling to the background task helper before closing storage
