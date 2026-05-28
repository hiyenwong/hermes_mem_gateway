## 1. Canonical Implementation Source

- [x] 1.1 Add an import/packaging test that asserts provider tests use `plugins.memory.layered_lancedb_sqlite` as the canonical implementation path.
- [x] 1.2 Decide whether root-level duplicate modules should be removed or kept as compatibility shims for one release cycle.
- [x] 1.3 Remove duplicate root-level behavior or replace root-level modules with thin imports from the canonical plugin package.
- [x] 1.4 Update README and architecture docs so they reference only the canonical plugin implementation path.
- [x] 1.5 Run the provider test suite and verify canonicalization did not change runtime behavior.

## 2. Policy Centralization

- [x] 2.1 Add `plugins/memory/layered_lancedb_sqlite/policy.py` with typed policy decision objects for shared intent, durable writes, and recall scopes.
- [x] 2.2 Move shared-intent resolution and shared-write authorization into the policy module while preserving current outcomes.
- [x] 2.3 Move durable promotion target-layer and target-principal decisions into the policy module.
- [x] 2.4 Move explicit memory-write target-layer and target-principal decisions into the policy module.
- [x] 2.5 Keep `namespace.py` focused on resolved identity, workspace, profile, session, platform, and metadata facts.
- [x] 2.6 Keep `governance.py` focused on candidate extraction, confidence, ranking, fingerprinting, and supersession heuristics.
- [x] 2.7 Add table-driven policy tests covering gateway, non-gateway, primary, non-primary, allowlisted, non-allowlisted, metadata shared intent, and natural-language shared intent cases.
- [x] 2.8 Run the provider and policy tests to verify no privacy or routing behavior regressed.

## 3. Provider Service Extraction

- [x] 3.1 Extract memory and user context formatting into `prompt_format.py` and preserve existing prompt output.
- [x] 3.2 Extract layered recall assembly and reinforcement into `recall_service.py`.
- [x] 3.3 Extract turn consolidation, duplicate detection, and supersession write flow into `promotion_service.py`.
- [x] 3.4 Extract explicit builtin memory mirroring into `memory_write_service.py`.
- [x] 3.5 Extract pending future tracking, draining, and background error reporting into `background.py`.
- [x] 3.6 Refactor the provider class so Hermes hooks resolve context and delegate to focused services.
- [x] 3.7 Add focused unit tests for each extracted service where behavior can be tested without full provider orchestration.
- [x] 3.8 Run the full provider test suite after each service extraction.

## 4. Verification And Cleanup

- [x] 4.1 Verify the refactor preserves SQLite storage paths, semantic index rebuild behavior, and Hermes-facing hook signatures.
- [x] 4.2 Run `openspec status --change refactor-memory-provider-architecture` and confirm the change remains apply-ready.
- [x] 4.3 Run the full test suite.
- [x] 4.4 Review changed files for accidental behavior changes outside canonicalization, policy extraction, and provider thinning.
