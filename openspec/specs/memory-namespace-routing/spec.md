# memory-namespace-routing Specification

## Purpose
TBD - created by archiving change add-layered-lancedb-sqlite-memory-provider. Update Purpose after archive.
## Requirements
### Requirement: Provider SHALL resolve memory scope from workspace, principal, and session context
The system SHALL derive memory read and write scope from configured workspace, runtime principal identity, session identity, and execution context rather than from a single flat memory namespace.

#### Scenario: Gateway runtime resolves user-isolated scope
- **WHEN** the provider is initialized for a gateway primary context with a stable `user_id`
- **THEN** it resolves a namespace that includes the configured workspace, the gateway principal identity, and the active session ID

#### Scenario: Non-gateway runtime resolves shared scope
- **WHEN** the provider is initialized for a non-gateway primary context
- **THEN** it resolves a namespace that includes the configured workspace, a shared principal marker, and the active session ID

### Requirement: Provider SHALL use stable identity for gateway user memory
The system SHALL use stable gateway identity values for user-scoped durable memory and SHALL NOT use display names or mutable usernames as the principal key.

#### Scenario: Stable identity is available
- **WHEN** Hermes provides a stable gateway `user_id`
- **THEN** the provider uses that value as the durable principal key for user semantic memory

#### Scenario: Stable identity is unavailable
- **WHEN** no stable gateway principal can be resolved
- **THEN** the provider blocks promotion into user semantic memory and records the turn only in safer scopes allowed by policy

### Requirement: Provider SHALL route recall by memory layer and namespace
The system SHALL retrieve recall candidates separately from session episodic, user semantic, and shared semantic layers using namespace-aware filtering before assembling provider context.

#### Scenario: Gateway recall includes layered candidates
- **WHEN** a gateway user requests memory-relevant context
- **THEN** the provider queries current-session episodic memory, same-user semantic memory, and workspace shared semantic memory separately before composing the result

#### Scenario: Non-gateway recall skips user semantic memory
- **WHEN** a non-gateway user requests memory-relevant context
- **THEN** the provider queries current-session episodic memory and workspace shared semantic memory without requiring a user semantic layer

### Requirement: Provider SHALL update active namespace on session switches
The system SHALL recompute active session-aware routing state when Hermes changes session identity mid-process.

#### Scenario: Resume or branch changes active session
- **WHEN** Hermes notifies the provider of `on_session_switch`
- **THEN** subsequent reads and writes use the new session identity and no longer target the previous session namespace

#### Scenario: Reset starts a new logical conversation
- **WHEN** Hermes signals a reset-style session switch
- **THEN** the provider clears or rotates any session-scoped buffers so new episodic writes do not attach to the previous conversation

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

