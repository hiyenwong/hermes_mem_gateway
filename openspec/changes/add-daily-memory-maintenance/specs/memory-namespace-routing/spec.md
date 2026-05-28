## ADDED Requirements

### Requirement: Maintenance jobs SHALL resolve user namespaces from Gateway identity fields
The system SHALL construct maintenance namespaces from stable Gateway identity fields using the same principal resolution rules as Gateway memory traffic.

#### Scenario: Maintenance uses email principal
- **WHEN** a maintenance job is invoked with a Gateway user email
- **THEN** the provider resolves that email as the user maintenance principal

#### Scenario: Maintenance falls back to user ID
- **WHEN** a maintenance job lacks Gateway user email but includes stable Gateway user ID
- **THEN** the provider resolves that user ID as the user maintenance principal

#### Scenario: Maintenance rejects display-name-only identity
- **WHEN** a maintenance job includes only a display name and no stable email or user ID
- **THEN** the provider does not run user maintenance for that identity

### Requirement: Maintenance recall and write scopes SHALL be principal-bound
The system SHALL bind all user maintenance storage access to the resolved maintenance namespace.

#### Scenario: Maintenance scope includes profile workspace principal and date
- **WHEN** a daily user maintenance job starts
- **THEN** its storage scope includes profile, workspace, resolved principal, operation kind, and date

#### Scenario: Maintenance context does not inherit active chat session
- **WHEN** user maintenance runs outside a normal chat turn
- **THEN** it uses a synthetic maintenance session ID and does not attach output to an unrelated active chat session
