## ADDED Requirements

### Requirement: Namespace resolution SHALL expose context facts without owning durable write policy
The system SHALL resolve profile, workspace, session, platform, principal identity, and request metadata as namespace facts, while durable write authorization and target-layer selection SHALL be owned by centralized policy decisions.

#### Scenario: Gateway identity is resolved as namespace fact
- **WHEN** a gateway request includes stable OpenWebUI identity fields
- **THEN** namespace resolution exposes the resolved principal identity and principal source without independently deciding final durable write target layer

#### Scenario: Non-gateway shared principal is resolved as namespace fact
- **WHEN** a non-gateway runtime initializes the provider
- **THEN** namespace resolution exposes the shared principal marker and workspace scope without independently deciding promotion authorization

### Requirement: Recall scope construction SHALL be explicit and testable
The system SHALL construct recall scopes through a dedicated policy or recall-scope decision so each layer query is explicit, ordered, and namespace-aware.

#### Scenario: Gateway recall scope is constructed
- **WHEN** an identified gateway user requests recall
- **THEN** the system constructs explicit session episodic, user semantic, and workspace shared semantic recall scopes before querying storage

#### Scenario: Non-gateway recall scope is constructed
- **WHEN** a non-gateway runtime requests recall
- **THEN** the system constructs explicit session episodic and workspace shared semantic recall scopes without requiring a user semantic scope
