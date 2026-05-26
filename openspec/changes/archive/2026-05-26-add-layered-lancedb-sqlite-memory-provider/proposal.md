## Why

Hermes memory provider plugins support persistent recall, but the current project needs a provider that can isolate memory by business workspace, gateway user identity, and conversation session without losing shared recall for non-gateway usage. A layered memory design is needed now so the provider can support both strict isolation and durable long-term recall, while remaining compatible with Hermes lifecycle hooks and avoiding known gateway/session pitfalls in upstream behavior.

## What Changes

- Add a new Hermes memory provider that uses SQLite as the source of truth for memory records, metadata, provenance, and lifecycle state.
- Add LanceDB-backed semantic retrieval for recall acceleration, with vectors indexed from selected memory records rather than treating the vector store as the system of record.
- Introduce a layered memory model with separate session episodic memory, gateway user semantic memory, and workspace shared semantic memory.
- Add namespace routing based on configured `memory_workspace`, Hermes runtime context, gateway `user_id`, and `session_id`.
- Add consolidation, decay, and supersession rules so short-lived session content can be promoted, archived, or replaced over time instead of accumulating as a flat memory corpus.
- Add provider behavior rules for gateway and non-gateway contexts, including shared memory for non-gateway usage and user-isolated memory for gateway usage.
- Add provider-side mirroring rules for builtin Hermes memory writes so curated memory entries can be captured in the layered store with provenance.

## Capabilities

### New Capabilities
- `layered-memory-provider`: Provide a Hermes-compatible external memory provider with layered recall, scoped isolation, and hybrid SQLite plus LanceDB storage.
- `memory-namespace-routing`: Resolve memory read/write scope from workspace, gateway user identity, session identity, and runtime agent context.
- `memory-lifecycle-governance`: Classify, consolidate, decay, supersede, and audit memory records across episodic and semantic layers.

### Modified Capabilities

## Impact

- Affects Hermes memory provider integration points, especially `initialize`, `prefetch`, `queue_prefetch`, `sync_turn`, `on_session_switch`, `on_session_end`, and `on_memory_write`.
- Introduces dependencies on SQLite-backed local persistence and LanceDB-backed semantic indexing.
- Defines new provider configuration for storage paths, workspace scoping, consolidation policy, and retrieval behavior.
- Requires implementation of namespace-aware recall and write policies for gateway, non-gateway, and non-primary agent contexts.
