## ADDED Requirements

### Requirement: Provider SHALL expose explicit daily maintenance operations
The system SHALL expose explicit provider service and CLI operations for daily user memory maintenance and SHALL NOT rely on an in-process provider timer for scheduling.

#### Scenario: Hermes triggers daily maintenance
- **WHEN** Hermes or an external scheduler invokes the daily maintenance command for a profile, workspace, and date
- **THEN** the provider runs maintenance through explicit service logic rather than a background timer started by normal provider initialization

#### Scenario: Operator retries one user
- **WHEN** an operator invokes user maintenance for a single Gateway user identity and date
- **THEN** the provider runs only that user's maintenance scope and does not process other principals

### Requirement: Daily user maintenance SHALL preserve principal isolation
The system SHALL run each user maintenance job with a Gateway-derived namespace and SHALL read and write only records matching the resolved profile, workspace, principal, and maintenance date scope.

#### Scenario: User compaction reads one principal
- **WHEN** maintenance runs for `user-a`
- **THEN** storage queries include `profile_id`, `workspace_id`, and `principal_id` for `user-a`

#### Scenario: User compaction writes same principal
- **WHEN** maintenance writes a compacted semantic user record
- **THEN** the record is written to `semantic_user` with the same principal resolved for the maintenance namespace

#### Scenario: Other user memory remains untouched
- **WHEN** maintenance runs for `user-a` while `user-b` has records in the same workspace
- **THEN** no `user-b` records are read, updated, archived, or reinforced by the `user-a` job

### Requirement: Daily maintenance SHALL be idempotent per user and date
The system SHALL record maintenance state per profile, workspace, principal, operation kind, and date so repeated executions are safe and auditable.

#### Scenario: Completed job is not duplicated
- **WHEN** daily maintenance is invoked again for a user and date already marked completed
- **THEN** the provider does not create duplicate compaction output for that same maintenance key

#### Scenario: Failed job can be retried
- **WHEN** a user maintenance job previously failed
- **THEN** a later invocation can retry that same maintenance key and update state to completed when successful

### Requirement: Daily maintenance SHALL keep shared memory separate
The system SHALL NOT update workspace shared memory during per-user daily maintenance unless a separate shared maintenance operation is explicitly invoked.

#### Scenario: Per-user maintenance does not write shared memory
- **WHEN** daily maintenance compacts a Gateway user's memory
- **THEN** the provider does not write `semantic_shared` records as part of that user job

#### Scenario: Shared maintenance is a separate operation
- **WHEN** shared workspace memory needs maintenance
- **THEN** it is handled by a distinct shared maintenance command with its own authorization and state tracking
