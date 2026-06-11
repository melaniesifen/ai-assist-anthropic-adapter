# AGENTS.md

## Repo Purpose

`ai-assist-anthropic-adapter` owns Anthropic-specific credential validation, Claude generation request mapping, streaming normalization, usage normalization, capabilities, and provider error mapping.

## Agent Instructions

- Read `README.md`, `ai-assist-platform-context.md`, and the provider sections in `../ai-assist-architecture/ai-workflow-assistant-platform-architecture-spec.md` before changing behavior.
- Use injected client boundaries. Do not call real Anthropic APIs in unit tests.
- Do not store provider keys. Decrypted keys should only pass through authorized provider-call paths.
- Do not log prompts, document context, model responses, provider keys, authorization headers, or raw provider errors that may contain sensitive content.
- Normalize provider errors to stable categories such as invalid credential, quota, rate limited, unavailable, context too large, policy blocked, and unknown provider error.
- Preserve Anthropic-specific stream metadata only after normalizing it into provider-neutral outputs.
- Add tests for credential validation, malformed requests, stream normalization, usage metadata, error mapping, and safe logging.

## Commands

- Run tests with `PYTHONPATH=src python3 -m unittest discover -s tests`.
- Use stdlib test tooling unless a later task adds repo-local dependencies.
- Keep tests split by source responsibility where practical; put shared fakes, constants, and assertions in `tests/common.py`.

## Review Notes

Before committing, review for prompt/key leakage, provider-specific details leaking into shared contracts, and ambiguous provider responses failing open.

## Commit Messages

All commits in this repo must use this format:

```text
docs/feat/fix/(or another appropriate type): title of change

problem: <description of problem>
solution: <description of solution>
impact: <impact of this change>
reference: <reference to this change in the docs if applicable>
```
