# Task Breakdown

Update this file as implementation progresses. Check off completed tasks in the same change that implements or verifies them.

Canonical cross-repo source: `../ai-assist-architecture/implementation-task-breakdown.md`.
Relevant design sources: provider adapter section in `../ai-assist-architecture/ai-workflow-assistant-platform-architecture-spec.md`, `../ai-assist-architecture/lld-auth-secrets-tenancy.md`, and `../ai-assist-architecture/lld-operations-safety.md`.

## Completed Bootstrap

- [x] Create dependency-light ESM package.
- [x] Implement injected Anthropic client boundary.
- [x] Implement credential validation wrapper.
- [x] Implement generation and stream normalization.
- [x] Preserve Anthropic final stream metadata in normalized output.
- [x] Implement usage/error normalization and safe logging helper.
- [x] Add unit tests using `node:test`.
- [x] Document tests and coverage commands.
- [x] Ignore local prompts, feedback, coverage output, dependencies, and build artifacts.

## Architecture Tasks

- [ ] REPO-001: Decide final language, runtime, package manager, and package/module layout for this adapter; distinguish current Node.js ESM bootstrap from production shape.
- [ ] PROVIDER-001: Align the local adapter contract with the shared provider interface from `ai-assist-contracts` once published.
- [x] PROVIDER-001: Support local injected-client methods for credential validation, generate response, stream response, usage metadata, and normalized provider errors.
- [x] PROVIDER-001: Keep prompt strategy, workflow selection, context retrieval, `SessionSecrets` storage, proposed actions, and session transport outside this repo.
- [ ] PROVIDER-001: Add shared provider contract tests with orchestration/contracts for validation, generation, streaming chunks, usage metadata, and error categories.
- [ ] PROVIDER-001: Add integration tests against the published provider contract and an Anthropic-compatible fake for validation, generate, stream, usage, and normalized errors.
- [ ] PROVIDER-003: Add a production Anthropic SDK or HTTP client wrapper behind the injected boundary.
- [ ] PROVIDER-003: Document and implement Anthropic credential-validation retry bounds and rate-limit behavior.
- [x] PROVIDER-003: Normalize Anthropic stream deltas and final stream metadata into provider-neutral stream output in the bootstrap adapter.
- [x] PROVIDER-003: Return usage metadata without logging raw prompts, context, model responses, or provider keys.
- [ ] PROVIDER-003: Normalize Anthropic quota, auth, model, timeout, and provider rate-limit failures to the shared error categories.
- [ ] PROVIDER-004: Surface expired or missing `SessionSecrets` as re-enter-key provider errors without attempting provider calls.
- [ ] PROVIDER-004: Return typed provider failures suitable for orchestration to emit through `SessionEvent` errors.
- [ ] AUTH-005: Support safe backend provider-key validation through this adapter without storing raw keys or logging raw provider errors.
- [ ] OPS-003: Verify metadata-only logging against the operations LLD allow-list and forbidden-field list.
- [ ] SAFE-003: Verify this adapter does not retain raw prompts, document context, model responses, screenshots, OCR text, accessibility trees, provider keys, or decrypted action payloads.

## E2E-Owned Validation Support

- [ ] E2E-001: Provide testable Anthropic key-validation behavior for onboarding without raw key leakage in logs.
- [ ] E2E-002: Provide testable Anthropic generate/stream behavior for the read/context/generate path.
- [ ] E2E-005: Provide test hooks or fixtures for provider quota, rate-limit, timeout, expired-secret, and metadata-only logging scenarios.
- [ ] E2E-005: Validate Anthropic outage, quota exhaustion, timeout, invalid model, invalid key, and provider rate-limit failure modes without raw prompt or key logging.

## Quality Tasks

- [ ] Raise line coverage to at least 95%.
- [ ] Add a deployment-style CI pipeline that runs install, lint or static checks, unit tests, integration tests, coverage, and package/build verification.
- [ ] Add deployment readiness checks for required Anthropic adapter environment variables, secret references, health checks, and metadata-only log configuration.
- [ ] Add Claude capability discovery or a curated Anthropic capability table.
- [ ] Add tool-use normalization if MVP workflows require it.
- [ ] Add provider-specific token usage and cost metadata where available.
- [ ] Add additional Anthropic model or modality support only when product scope requires it.
