## ADDED Requirements

### Requirement: Gateway shared-memory writes SHALL require both authorization and explicit intent
The system SHALL allow gateway requests to write shared durable memory only when the caller email is on an allowlist and the request explicitly requests shared persistence.

#### Scenario: Allowlisted gateway user explicitly requests shared memory
- **WHEN** a gateway request is sent by an allowlisted user email and explicit shared intent is resolved as true
- **THEN** the provider may promote eligible content into shared durable memory

#### Scenario: Non-allowlisted gateway user requests shared memory
- **WHEN** a gateway request explicitly asks for shared memory but the caller email is not allowlisted
- **THEN** the provider does not promote the content into shared durable memory

### Requirement: Shared intent resolution SHALL prioritize metadata over natural-language directives
The system SHALL support explicit shared-intent resolution from both request metadata and natural-language directives, and SHALL treat metadata as the higher-priority source when both are present.

#### Scenario: Metadata requests shared while text does not
- **WHEN** request metadata explicitly marks content for shared persistence
- **THEN** the provider treats the request as an explicit shared-memory request regardless of natural-language absence

#### Scenario: Metadata denies shared while text requests it
- **WHEN** request metadata does not authorize shared persistence and natural-language content includes a shared-memory directive
- **THEN** the provider follows the metadata result as the authoritative explicit-intent source
