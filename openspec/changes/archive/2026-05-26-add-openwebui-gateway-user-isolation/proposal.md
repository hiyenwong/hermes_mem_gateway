## Why

The current provider supports user-scoped gateway memory in principle, but it does not yet define a reliable attribution path for OpenWebUI traffic. This change is needed so gateway users are always isolated by default, and so shared memory writes can occur only through explicit, authorized actions rather than by accidental promotion of private user requests.

## What Changes

- Add OpenWebUI-aware gateway identity resolution from `X-OpenWebUI-User-*` headers into provider runtime context.
- Add a deterministic principal resolution policy for gateway traffic that uses stable user identity for durable private memory and rejects unsafe fallbacks for shared writes.
- Change gateway memory policy to `private by default` for all identified users, including episodic, semantic user memory, and prompt-scoped behavioral context.
- Add shared-memory authorization rules so gateway requests can write shared memory only when the caller email is allowlisted in configuration and the request explicitly asks for shared persistence.
- Add explicit shared-intent resolution with two supported sources: request metadata and natural-language commands, with metadata taking priority.
- Add minimal prompt context injection for OpenWebUI user identity and privacy scope without exposing raw headers to the model.

## Capabilities

### New Capabilities

### Modified Capabilities
- `memory-namespace-routing`: Extend gateway identity resolution to support OpenWebUI header-derived principals, explicit private-by-default routing, and shared-write authorization inputs.
- `memory-lifecycle-governance`: Restrict gateway durable promotion so private user requests never promote into shared memory unless explicitly authorized and explicitly requested.
- `layered-memory-provider`: Add OpenWebUI-derived prompt context injection and gateway-specific write/read handling based on resolved identity and shared-write policy.

## Impact

- Affects provider initialization, runtime namespace resolution, and gateway prompt composition.
- Adds configuration for shared-writer email allowlists and explicit shared-write policy.
- Requires plumbing OpenWebUI user identity and shared-intent metadata through gateway-facing request handling into provider kwargs or equivalent runtime context.
- Changes gateway memory behavior so normal user requests can no longer implicitly write shared durable memory.
