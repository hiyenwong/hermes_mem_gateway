## Context

The provider already supports layered memory with session episodic memory, user semantic memory, and workspace shared semantic memory. However, OpenWebUI gateway traffic introduces a stronger isolation requirement: every gateway user request must be private by default, and shared memory writes must be impossible unless both the caller identity and the caller intent explicitly authorize them.

This creates a cross-cutting design problem across gateway request handling, runtime namespace resolution, memory promotion policy, and prompt construction:

- Gateway traffic arrives with OpenWebUI-specific headers rather than a guaranteed normalized Hermes user principal.
- User identity must be resolved into a stable private principal for memory attribution.
- User display information can be useful for prompt behavior shaping but must not be used as the durable isolation key.
- Shared memory must no longer be an automatic promotion target for normal gateway requests.

The current provider architecture can support this change without replacing the storage model. The main gaps are identity normalization, shared-write authorization policy, and prompt-scoped privacy context injection.

## Goals / Non-Goals

**Goals:**

- Resolve OpenWebUI gateway identity from request metadata into a stable private principal.
- Make all gateway requests private by default for episodic memory, semantic user memory, and prompt-scoped behavior shaping.
- Allow shared memory writes for gateway traffic only when the caller email is allowlisted and the request explicitly requests shared persistence.
- Support two explicit shared-intent sources: metadata and natural-language directives, with metadata taking precedence.
- Inject minimal user/privacy context into prompts without exposing raw gateway headers.

**Non-Goals:**

- Infer shared intent from vague or generic language.
- Use display names as durable memory principals.
- Store raw HTTP headers verbatim in provider prompt context.
- Automatically share technically useful content just because it resembles project knowledge.
- Redesign the SQLite plus LanceDB storage model or the layered-memory architecture.

## Decisions

### 1. Normalize OpenWebUI identity before memory policy is evaluated

Gateway handling will extract OpenWebUI user identity from incoming request context and normalize it into standard provider runtime fields. The provider will use:

- `resolved_user_email` as the preferred stable principal source
- `resolved_user_id` as the fallback stable principal source
- `resolved_user_name` only for prompt presentation

Rationale:

- Email is both human-auditable and typically stable in managed OpenWebUI deployments.
- User ID is a stronger fallback than display name.
- Display names are mutable and unsuitable for durable isolation keys.

Alternatives considered:

- Using display name as a principal fallback was rejected because it creates unstable isolation boundaries.
- Passing raw headers directly into memory routing was rejected because it couples provider policy to transport details.

### 2. Treat all gateway requests as private unless shared authorization succeeds

For gateway traffic, the default memory policy will be:

- session writes: private to the resolved principal and session
- durable user memory writes: private to the resolved principal
- durable shared memory writes: forbidden by default

Shared writes become legal only if both conditions are true:

- the caller email is allowlisted in configuration
- the request explicitly requests shared persistence

Rationale:

- The user requirement is that any gateway user's request must remain their own unless explicitly elevated.
- This avoids accidental contamination of shared memory by private preferences, instructions, or per-user task context.

Alternatives considered:

- Auto-sharing by content classification was rejected because it is too error-prone for isolation-critical behavior.
- Allowing all authenticated gateway users to write shared memory was rejected because authorization and intent would be conflated.

### 3. Use explicit shared-intent resolution with metadata priority

The system will support two shared-intent sources:

- request metadata flags
- natural-language directives in user content

Metadata wins whenever both are present.

Rationale:

- Metadata allows trusted upstream systems to request shared writes deterministically.
- Natural-language support preserves usability for human operators.
- Metadata priority avoids ambiguity when content and upstream controls disagree.

Alternatives considered:

- Natural-language-only control was rejected because it is too easy to spoof or phrase ambiguously.
- Metadata-only control was rejected because operators also need direct conversational control.

### 4. Keep prompt injection minimal and scoped

The provider will inject a minimal user context block for gateway requests that includes:

- authenticated-user flag
- display name if available
- privacy scope
- whether shared write was requested
- whether shared write is authorized

It will not inject raw OpenWebUI headers.

Rationale:

- The model needs enough context to avoid treating user-specific instructions as globally shared behavior.
- Raw header exposure is unnecessary and expands the prompt attack surface.

Alternatives considered:

- No prompt injection was rejected because some behavior isolation requirements are not purely storage-related.
- Full header passthrough was rejected because it leaks transport-level details into model context.

### 5. Record attribution provenance alongside memory writes

When gateway identity and shared-intent resolution occur, the provider will store provenance metadata describing:

- resolved principal source
- whether gateway handling was active
- whether shared was requested
- whether shared was authorized

Rationale:

- This supports debugging, auditing, and future incident analysis when a record appears in the wrong scope.

Alternatives considered:

- Relying only on final `principal_id` was rejected because it loses the reasoning chain behind the policy decision.

## Risks / Trade-offs

- [Gateway may not always provide email] -> Fall back to resolved user ID for private durable memory, but never use display name as the durable principal.
- [Natural-language shared triggers may be spoofed or ambiguous] -> Restrict shared phrases to a small allowlist and require authorization in addition to intent.
- [Metadata may conflict with user text] -> Give metadata higher priority and record the chosen source in provenance.
- [Prompt injection may accidentally overexpose user identity] -> Inject only minimal display and policy context, not raw headers or full identity payloads.
- [Shared memory may become inaccessible when allowlists are too strict] -> Keep the allowlist configurable and add explicit tests for authorized shared-write flows.

## Migration Plan

1. Add configuration for allowlisted shared-writer emails and explicit shared-write policy.
2. Add OpenWebUI identity extraction and normalized gateway runtime fields.
3. Update namespace resolution and gateway write policy to enforce private-by-default routing.
4. Add shared-intent resolution from metadata and natural language with metadata precedence.
5. Add prompt context injection and provenance metadata for gateway-derived identity and authorization.
6. Add tests covering private routing, unauthorized shared attempts, and authorized shared writes.

Rollback strategy:

- Disable OpenWebUI-specific normalization and fall back to existing gateway/private behavior.
- Preserve stored records and provenance regardless of policy rollback.
- Keep shared authorization controls configuration-driven so behavior can be tightened or relaxed without schema replacement.

## Open Questions

- What exact metadata key path should upstream gateway code use for shared intent so it remains stable across integrations?
- Should unauthorized shared requests be silently downgraded to private memory or emit a visible warning/tool event?
- Should non-gateway contexts also support the same explicit shared-intent policy in a future change, or remain under the current behavior?
