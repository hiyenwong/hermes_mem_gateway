## ADDED Requirements

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
