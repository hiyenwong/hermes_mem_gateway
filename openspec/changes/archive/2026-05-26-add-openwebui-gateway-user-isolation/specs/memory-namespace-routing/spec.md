## ADDED Requirements

### Requirement: Gateway OpenWebUI traffic SHALL resolve stable private principals from normalized identity fields
The system SHALL resolve gateway memory principals from stable OpenWebUI-derived identity fields, preferring resolved email, then resolved user ID, and SHALL NOT use display names as durable principal keys.

#### Scenario: Gateway request resolves principal from email
- **WHEN** a gateway request includes a normalized OpenWebUI user email
- **THEN** the provider uses that email-derived value as the private durable principal for user-scoped memory

#### Scenario: Gateway request falls back to user ID
- **WHEN** a gateway request lacks a normalized OpenWebUI user email but includes a normalized user ID
- **THEN** the provider uses the user ID as the private durable principal and does not fall back to display name

### Requirement: Gateway requests SHALL be private by default
The system SHALL route all gateway requests to private user scopes by default and SHALL NOT treat normal gateway requests as shared-memory candidates.

#### Scenario: Normal gateway request stays private
- **WHEN** an identified gateway user sends a normal request without explicit shared authorization
- **THEN** the provider stores episodic and durable user memory only in the private user scope for that principal

#### Scenario: Gateway request without stable principal does not become shared durable memory
- **WHEN** a gateway request does not provide a stable principal
- **THEN** the provider does not promote the request into shared durable memory by default
