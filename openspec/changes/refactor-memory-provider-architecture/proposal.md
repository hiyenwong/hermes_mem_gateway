## Why

The layered memory provider has working behavior, but its implementation now has duplicate module paths and policy-sensitive decisions spread across provider, namespace, and governance code. This change reduces policy drift risk, makes Gateway privacy behavior auditable, and prepares the provider for safer future extensions.

## What Changes

- Canonicalize the provider implementation so config, namespace, governance, storage, CLI, and provider behavior have one editable source.
- Remove root-level duplicate modules or convert them to thin compatibility shims that delegate to the canonical plugin package.
- Centralize durable write, shared-write, target-layer, and principal-selection policy into a dedicated policy layer.
- Move provider-internal recall, promotion, explicit memory mirroring, prompt formatting, and background task handling into focused services.
- Preserve existing public provider hooks, storage paths, and current behavioral guarantees unless explicitly changed by the modified specs.
- Add focused tests for canonical imports, policy decision tables, and extracted provider services.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `layered-memory-provider`: clarify canonical implementation ownership and the provider adapter/service split required to preserve behavior while reducing orchestration complexity.
- `memory-namespace-routing`: clarify that namespace resolution supplies identity and scope inputs, while policy owns durable write and target-layer decisions.
- `memory-lifecycle-governance`: clarify that lifecycle promotion and shared-memory authorization use centralized, testable policy decisions with audit metadata.

## Impact

- Affected code: root-level duplicate modules, `plugins/memory/layered_lancedb_sqlite/__init__.py`, `namespace.py`, `governance.py`, storage callers, and tests.
- Affected docs: README and architecture documentation should reference the canonical plugin package only.
- APIs: Hermes-facing provider hooks remain stable.
- Storage: SQLite and LanceDB/stub storage formats remain unchanged for this refactor.
- Dependencies: no new runtime dependency is expected.
