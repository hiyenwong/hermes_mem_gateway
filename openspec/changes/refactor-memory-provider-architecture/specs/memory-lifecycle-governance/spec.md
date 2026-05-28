## ADDED Requirements

### Requirement: Durable write decisions SHALL be centralized and auditable
The system SHALL resolve durable memory write authorization, target layer, target principal, shared authorization, and denial reason through centralized policy decisions instead of scattered provider, namespace, or governance conditionals.

#### Scenario: Promotion asks policy for target
- **WHEN** a classified memory candidate is eligible for durable promotion by confidence
- **THEN** the promotion flow asks the policy module for the durable write decision before writing semantic memory

#### Scenario: Explicit memory write asks policy for target
- **WHEN** Hermes emits an explicit memory write event
- **THEN** the memory write flow asks the policy module for the target layer and principal before mirroring the memory

#### Scenario: Policy decision includes audit details
- **WHEN** policy allows or denies a durable shared-memory write
- **THEN** the decision includes stable reason and metadata fields that can be tested and, when a write occurs, persisted with provenance

### Requirement: Policy SHALL be covered by table-driven execution-context tests
The system SHALL test durable write and shared-memory policy across gateway, non-gateway, primary, non-primary, allowlisted, non-allowlisted, metadata shared intent, and natural-language shared intent combinations.

#### Scenario: Gateway policy matrix is tested
- **WHEN** policy tests run for gateway contexts
- **THEN** they verify private, shared, denied, allowlisted, and non-allowlisted outcomes without requiring provider orchestration

#### Scenario: Non-primary policy matrix is tested
- **WHEN** policy tests run for non-primary execution contexts
- **THEN** they verify that durable writes remain blocked by default unless configuration explicitly allows the tested path
