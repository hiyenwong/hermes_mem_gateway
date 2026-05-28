## ADDED Requirements

### Requirement: Maintenance context SHALL allow same-principal user maintenance writes
The system SHALL allow a dedicated maintenance execution context to write durable user maintenance records only within the same resolved principal scope.

#### Scenario: Maintenance writes user summary
- **WHEN** maintenance compacts records for an identified Gateway user
- **THEN** policy allows writing the compaction output to `semantic_user` for that same principal

#### Scenario: Maintenance cannot write another user
- **WHEN** maintenance is running for one resolved principal
- **THEN** policy prevents writing durable user records for any different principal

#### Scenario: Maintenance does not default to shared
- **WHEN** maintenance runs for an identified Gateway user without an explicit shared maintenance operation
- **THEN** policy prevents writing to `semantic_shared`

### Requirement: Maintenance writes SHALL preserve provenance and audit metadata
The system SHALL record provenance metadata for maintenance writes that identifies operation kind, maintenance date, profile, workspace, principal, and maintenance state key.

#### Scenario: Compaction output records provenance
- **WHEN** maintenance writes a compacted memory record
- **THEN** the record provenance identifies the write as daily maintenance and includes the maintenance date and state key

#### Scenario: Maintenance archival records reason
- **WHEN** maintenance archives or supersedes stale records
- **THEN** the provider records metadata explaining the maintenance reason and operation kind

### Requirement: Maintenance policy SHALL be tested separately from chat policy
The system SHALL cover maintenance execution context with policy tests separate from normal primary and subagent chat contexts.

#### Scenario: Same-principal maintenance path is tested
- **WHEN** policy tests run for maintenance context
- **THEN** they verify same-principal `semantic_user` writes are allowed

#### Scenario: Shared and cross-principal maintenance paths are tested
- **WHEN** policy tests run for maintenance context
- **THEN** they verify shared default writes and cross-principal writes are denied
