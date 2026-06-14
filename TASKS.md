# Task Breakdown

Update this file as implementation progresses. Check off completed tasks in the same change that implements or verifies them.

Canonical cross-repo source: `../ai-assist-architecture/implementation-task-breakdown.md`.
Relevant design sources: provider adapter section in `../ai-assist-architecture/ai-workflow-assistant-platform-architecture-spec.md`, `../ai-assist-architecture/lld-auth-secrets-tenancy.md`, and `../ai-assist-architecture/lld-operations-safety.md`.

## Completed Bootstrap And Migration

- [x] Created initial dependency-light Node.js ESM bootstrap package; superseded by the REPO-002 Python migration.
- [x] Implement injected Anthropic client boundary.
- [x] Implement credential validation wrapper.
- [x] Implement generation and stream normalization.
- [x] Preserve Anthropic final stream metadata in normalized output.
- [x] Implement usage/error normalization and safe logging helper.
- [x] Port unit tests from `node:test` coverage to stdlib Python `unittest`.
- [x] Document current Python test command.
- [x] Ignore local prompts, feedback, coverage output, dependencies, and build artifacts.

## Architecture Tasks

- [ ] REPO-001: Decide final package manager and package/module layout for this Python adapter; preserve the record that the prior Node.js ESM package was a temporary bootstrap.
- [x] REPO-002: Migrate this adapter from the temporary Node.js ESM bootstrap to Python, preserving or intentionally superseding current validation, generation, streaming, final stream metadata, usage normalization, error normalization, safe logging, and tests.
- Migration gate: Python migration is complete; pause broad new Anthropic adapter feature work until a parent/user targeting pass selects specific next tasks. REPO-001 remains open for package manager and package/module layout decisions.
- [ ] PROVIDER-001: Align the local adapter contract with the shared provider interface from `ai-assist-contracts` once published.
- [x] PROVIDER-001: Support local injected-client methods for credential validation, generate response, stream response, usage metadata, and normalized provider errors.
- [x] PROVIDER-001: Keep prompt strategy, workflow selection, context retrieval, `SessionSecrets` storage, proposed actions, and session transport outside this repo.
- [ ] PROVIDER-001: Add shared provider contract tests with orchestration/contracts for validation, generation, streaming chunks, usage metadata, and error categories.
- [ ] PROVIDER-001: Add integration tests against the published provider contract and an Anthropic-compatible fake for validation, generate, stream, usage, and normalized errors.
- [ ] PROVIDER-003: Add a production Anthropic SDK or HTTP client wrapper behind the injected boundary.
- [ ] PROVIDER-003: Document and implement Anthropic credential-validation behavior that is safe to rate-limit and retry only within documented bounds.
- [x] PROVIDER-003: Support platform-owned provider access metadata as the default generation and stream path without requiring user-pasted credentials.
- [x] PROVIDER-003: Normalize Anthropic stream deltas and final stream metadata into provider-neutral stream output in the Python adapter.
- [x] PROVIDER-003: Return usage metadata without logging raw prompts, context, model responses, or provider keys.
- [x] PROVIDER-003: Normalize Anthropic quota, auth, model, timeout, and provider rate-limit failures to the shared error categories.
- [ ] PROVIDER-004: Surface expired or missing `SessionSecrets` as re-enter-key provider errors without attempting provider calls.
- [ ] PROVIDER-004: Return typed provider failures suitable for orchestration to emit through `SessionEvent` errors.
- [ ] AUTH-005: Support safe backend provider-key validation through this adapter without storing raw keys or logging raw provider errors.
- [ ] OPS-003: Verify metadata-only logging against the operations LLD allow-list and forbidden-field list.
- [ ] SAFE-003: Verify this adapter does not retain raw prompts, document context, model responses, screenshots, OCR text, accessibility trees, provider keys, or decrypted action payloads.

## E2E-Owned Validation Support

- [ ] E2E-001: Provide testable Anthropic key-validation behavior for onboarding without raw key leakage in logs.
- [ ] E2E-002: Provide testable Anthropic generate/stream behavior for the read/context/generate path.
- [x] E2E-005: Provide test hooks or fixtures for provider quota, rate-limit, timeout, missing access, optional BYO, platform access, and metadata-only logging scenarios.
- [ ] E2E-005: Validate Anthropic outage, quota exhaustion, timeout, invalid model, invalid key, and provider rate-limit failure modes without raw prompt or key logging.

## M8 Provider Access Evidence

- [x] M8-T4.1: Anthropic adapter accepts platform-owned provider access metadata for generation and streaming without user-pasted credentials.
- [x] M8-T4.2: Anthropic provider status helper reports available, unavailable, misconfigured, quota-limited, optional BYO, and deferred states without secrets.
- [x] M8-T4.3: BYO credential handling remains explicit and optional; missing provider access fails closed.
- [x] M8-T4.5: Anthropic adapter matches the provider-access contract and can safely report deferred/unavailable status through metadata.
- [x] M8-T4.7: Added provider-access tests for platform access, optional BYO, missing access, status metadata, and safe logs.

## Milestone 5: Ask And Stream

- [x] M5-T4.2: Verified Anthropic fake stream tests for deterministic deltas, final response, usage metadata, safe errors, and empty or unknown terminal stream behavior.
- [x] M5-T4.3: Verified Anthropic provider-neutral stream output names and provider error categories used by contracts and orchestration.
- [x] M5-T4.4: Verified Anthropic adapter logs metadata only, including default safe logger usage metadata, without raw prompts, model response bodies, provider keys, or secret material.
- [x] M5-T4.5: Updated Anthropic adapter task tracking for M5-T4 evidence.
- [x] M5-T4.6: Run Anthropic adapter tests and compile checks after review feedback is resolved.
- [x] M5-T4.7: Write fresh review feedback for the current Anthropic adapter diff and resolve or document findings.

## Quality Tasks

- [ ] Raise line coverage to at least 95%.
- [ ] Add a deployment-style CI pipeline that runs install, lint or static checks, unit tests, integration tests, coverage, and package/build verification.
- [ ] Add deployment readiness checks for required Anthropic adapter environment variables, secret references, health checks, and metadata-only log configuration.
- [ ] Add Claude capability discovery or a curated Anthropic capability table.
- [ ] Add tool-use normalization if MVP workflows require it.
- [ ] Add provider-specific token usage and cost metadata where available.
- [ ] Add additional Anthropic model or modality support only when product scope requires it.
