## 1. Gateway Identity Normalization

- [x] 1.1 Add OpenWebUI-aware identity extraction for `X-OpenWebUI-User-Email`, `X-OpenWebUI-User-Id`, and `X-OpenWebUI-User-Name`
- [x] 1.2 Normalize extracted gateway identity into stable runtime fields for email, user ID, display name, and resolved principal
- [x] 1.3 Update namespace routing so gateway requests are private by default and never use display name as the durable principal

## 2. Shared Authorization Policy

- [x] 2.1 Add configuration for allowlisted shared-writer emails and explicit shared-write policy
- [x] 2.2 Implement explicit shared-intent resolution from metadata and natural-language directives with metadata precedence
- [x] 2.3 Enforce gateway shared-write policy so shared durable memory is allowed only for allowlisted emails with explicit shared intent

## 3. Prompt and Provenance Handling

- [x] 3.1 Add minimal gateway user prompt context injection without exposing raw OpenWebUI headers
- [x] 3.2 Persist provenance metadata for resolved principal source, gateway policy, shared intent source, and shared authorization result
- [x] 3.3 Ensure unauthorized or non-explicit gateway requests remain private in both memory writes and prompt-scoped behavior context

## 4. Verification

- [x] 4.1 Add tests for OpenWebUI email and user-ID principal resolution, including display-name exclusion from durable identity
- [x] 4.2 Add tests for private-by-default gateway routing and blocked shared writes for non-allowlisted users
- [x] 4.3 Add tests for allowlisted explicit shared writes, metadata-over-natural-language precedence, and prompt context sanitization
