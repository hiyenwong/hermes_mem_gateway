# memory-lifecycle-governance Specification

## Purpose
TBD - created by archiving change add-layered-lancedb-sqlite-memory-provider. Update Purpose after archive.
## Requirements
### Requirement: Provider SHALL classify new memory candidates before durable promotion
The system SHALL treat newly synchronized turns as candidate memory inputs and SHALL classify them before promoting content into durable semantic layers.

#### Scenario: Temporary session content remains episodic
- **WHEN** a synchronized turn contains transient task state or unverified short-lived context
- **THEN** the provider keeps the extracted content in episodic storage without promoting it into durable semantic memory

#### Scenario: Stable high-value content is promoted
- **WHEN** a synchronized turn contains stable preferences, identity facts, repeated project knowledge, or explicit memory instructions
- **THEN** the provider promotes the extracted content into the appropriate semantic layer based on scope rules

### Requirement: Provider SHALL apply conservative durable write policy by execution context
The system SHALL restrict durable semantic writes to safe execution contexts and SHALL prevent non-primary agent contexts from polluting long-term user memory by default.

#### Scenario: Primary agent may promote durable memory
- **WHEN** the provider handles a turn from a primary agent context
- **THEN** it may promote eligible memory into durable semantic layers

#### Scenario: Subagent does not write long-term memory
- **WHEN** the provider handles a delegated or non-primary subagent context
- **THEN** it does not promote new durable user or shared semantic memory unless explicitly allowed by policy

### Requirement: Provider SHALL preserve provenance and supersession history
The system SHALL keep provenance metadata for memory writes and SHALL record version relationships when newer durable facts replace older ones.

#### Scenario: Builtin memory write is mirrored with provenance
- **WHEN** Hermes emits an `on_memory_write` event for builtin memory
- **THEN** the provider stores the mirrored entry with source metadata that identifies the write origin and execution context

#### Scenario: Updated preference supersedes older durable memory
- **WHEN** a newer durable memory conflicts with an older stable durable record for the same subject
- **THEN** the provider creates a replacement relationship that preserves the older record's history while prioritizing the newer record for recall

### Requirement: Provider SHALL support decay and archival of low-value memory
The system SHALL track recency, access, and reinforcement signals so low-value memory can be down-ranked or archived over time without deleting the canonical audit trail.

#### Scenario: Low-value memory leaves the primary recall path
- **WHEN** a durable memory record becomes stale, low-reinforcement, and low-importance under configured policy
- **THEN** the provider archives or down-ranks it so it no longer dominates primary semantic recall

#### Scenario: Archived memory remains recoverable
- **WHEN** an archived memory record is needed for audit, repair, or deep retrieval
- **THEN** the provider can recover it from canonical storage even if it is absent from the primary semantic index

