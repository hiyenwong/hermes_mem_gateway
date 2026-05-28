## Context

The provider currently has a functional layered memory architecture: SQLite is authoritative, LanceDB or the stub index supports semantic lookup, namespace routing separates session, user, and shared scopes, and lifecycle governance decides which turns become durable memory.

The main architecture issue is not missing behavior; it is implementation shape. Root-level modules and plugin package modules overlap, and policy-sensitive rules are distributed across namespace resolution, governance helpers, and provider methods. This makes future Gateway privacy changes harder to audit and increases the chance that one import path or write path drifts from another.

The refactor must preserve current Hermes-facing hooks, storage paths, SQLite schema, semantic index rebuild behavior, and existing provider tests while creating a cleaner internal architecture.

## Goals / Non-Goals

**Goals:**

- Establish `plugins/memory/layered_lancedb_sqlite/` as the canonical implementation path.
- Remove or shim duplicate root-level modules so policy and behavior exist in one editable implementation.
- Centralize durable write, shared write, target layer, and principal-selection decisions in one policy module.
- Thin the provider class into a Hermes adapter and lifecycle coordinator.
- Extract recall, promotion, explicit memory write mirroring, prompt formatting, and background task handling into focused modules.
- Add tests that make canonical imports, policy decisions, and extracted services explicit.

**Non-Goals:**

- Changing SQLite schema or existing storage location layout.
- Replacing LanceDB/stub indexing behavior.
- Introducing a new embedding provider or retrieval algorithm.
- Changing Hermes public provider hook names or signatures.
- Redesigning memory extraction heuristics beyond moving ownership boundaries.

## Decisions

### Decision: Use the plugin package as the canonical source

The canonical implementation will live under `plugins/memory/layered_lancedb_sqlite/`. Root-level duplicate modules will either be removed or converted to compatibility shims that import from the plugin package.

Rationale: packaging already includes `plugins*`, and tests import the provider from the plugin package. Keeping the plugin package authoritative aligns local tests, package metadata, and Hermes loading.

Alternative considered: keep both trees and manually synchronize them. This keeps short-term compatibility but preserves the policy drift risk that motivated the change.

### Decision: Introduce a dedicated policy module

Policy decisions will move into a dedicated `policy.py` module with typed decision results. Candidate types include:

- `WriteDecision`: allowed flag, target layer, target principal, reason, and audit metadata.
- `SharedIntentDecision`: requested flag and source.
- `RecallScope`: ordered layer/scope queries used by recall assembly.

Rationale: Gateway privacy and shared-write authorization are security-sensitive. A centralized policy module makes decision tables testable and keeps `namespace.py` focused on identity/scope facts.

Alternative considered: leave policy in provider helper methods. That avoids new files but continues mixing interface orchestration with privacy decisions.

### Decision: Keep namespace resolution descriptive, not prescriptive

`namespace.py` will continue to resolve runtime facts such as profile, workspace, session, platform, principal identity, and request metadata. It will not be the final owner of durable write authorization or target-layer selection.

Rationale: separating facts from decisions makes it easier to test "what context did we resolve?" independently from "what is this context allowed to do?"

Alternative considered: put all policy in namespace resolution. That makes a single object convenient but overloads namespace resolution and duplicates governance decisions.

### Decision: Extract provider services incrementally

The provider class will delegate to focused services:

- `recall_service.py` for layered recall, reinforcement, and context assembly.
- `promotion_service.py` for turn candidate promotion, duplicate checks, and supersession.
- `memory_write_service.py` for builtin memory mirroring.
- `prompt_format.py` for user and memory context formatting.
- `background.py` for pending future tracking, draining, and error reporting.

Rationale: the provider should adapt Hermes hooks to internal services. This reduces review scope and lets tests target smaller behavior units.

Alternative considered: a larger rewrite into repository/service interfaces. That is unnecessary now because storage backend behavior is not changing.

### Decision: Preserve storage behavior during the refactor

`SQLiteStore` remains the storage boundary for this change. The refactor may adjust callers and tests, but it will not introduce schema migrations or change index rebuild semantics.

Rationale: storage consistency is important, and mixing schema changes into a structural refactor would increase risk.

Alternative considered: add repository interfaces and migration infrastructure now. Those are valuable later but not required for the stated architecture cleanup.

## Risks / Trade-offs

- Import compatibility risk -> keep thin root-level shims only if external callers still rely on root imports, and add tests that make the chosen import path explicit.
- Policy behavior regression -> create policy table tests before moving provider branches and run existing provider tests after each extraction.
- Over-fragmentation -> extract services only around existing cohesive workflows and avoid introducing abstract interfaces until there is a second implementation or clear testing need.
- Async behavior regression -> isolate background future tracking and test drain/error behavior separately from promotion logic.
- Documentation drift -> update README and architecture docs after canonicalization so docs name only the canonical package.

## Migration Plan

1. Add canonical import tests that document the expected provider package path.
2. Remove or shim duplicate root-level modules.
3. Extract policy decisions and add table-driven tests for Gateway, CLI, primary, non-primary, allowlist, and shared-intent combinations.
4. Move recall assembly into `recall_service.py` while preserving output format.
5. Move promotion and explicit memory write mirroring into focused services.
6. Move prompt formatting and background future tracking into focused helpers.
7. Run the full provider test suite after each step.

Rollback strategy: because storage schema and public hooks remain unchanged, rollback can be performed by reverting the refactor commits without data migration.

## Open Questions

- Should root-level modules be removed outright, or should they remain as compatibility shims for one release cycle?
- Should policy reason strings become part of persisted metadata for all denied writes, or only successful writes?
- Should background task errors be exposed only through validation output, or also through provider prompt/system diagnostics?
