# ai-assist-anthropic-adapter

Anthropic provider adapter for the AI Assist Platform.

This package owns Anthropic-specific credential validation, Claude generation request mapping, streaming event normalization, usage normalization, capability metadata, and safe provider error mapping. It does not own provider key storage, prompt construction, context retrieval, proposed actions, document mutation, or session transport.

## Current Boundary

- Runtime: dependency-light Python package.
- Tests: stdlib `unittest`.
- Network: no direct provider calls in this bootstrap.
- Provider access: injected client only.
- Logging: metadata allow-list only; raw prompts, message content, provider keys, tokens, model outputs, and raw provider errors are rejected from adapter logs.

The orchestration service should pass a decrypted short-lived session secret to this adapter only for the duration of a provider call. The adapter never stores the credential and never returns it.

## Public Shape

```python
from ai_assist_anthropic_adapter import create_anthropic_adapter

adapter = create_anthropic_adapter(client=client)
```

Adapter methods:

- `await validate_credential({ "credential": "...", "requestId": "...", "correlationId": "..." })`
- `await generate({ "credential": "...", "model": "...", "messages": [...], "temperature": 0.2, "maxOutputTokens": 512 })`
- `stream({ "credential": "...", "model": "...", "messages": [...] })`
- `get_capabilities()`

The injected client must provide:

- `validate_credential(request)`
- `generate(request)`
- `stream(request)`

The adapter accepts sync or async client results. `stream` may return a sync iterable or async iterable of raw Anthropic events.

All provider responses are normalized to platform-facing shapes. Provider errors are mapped to stable categories and safe codes before being returned or logged.

## Future SDK/HTTP Adapter

A future production client can wrap the Anthropic SDK or a minimal HTTP client behind the injected interface:

- `validate_credential` should make a low-cost server-side validation request and return metadata only.
- `generate` should return raw Anthropic response metadata needed for normalization.
- `stream` should return an async iterable of raw Anthropic stream events.

The client wrapper, not this adapter contract, owns SDK initialization, HTTP timeouts, retries, and provider endpoint details.

## Service Boundary

This repo is an internal provider-adapter service boundary. Orchestration owns workflow decisions, prompt assembly, context consent enforcement, and proposed-action creation. This adapter owns only Anthropic-specific provider translation and returns no raw prompt or output content in logs.

## Task Breakdown

Implementation tasks are tracked in [TASKS.md](TASKS.md). Update the checkboxes there in the same change that implements or verifies a task.

## Testing And Coverage

Run the unit tests:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests
```

No third-party test dependencies are required for the current package. If later tooling writes coverage, HTML, JUnit, or build output, those generated paths are ignored by `.gitignore`.
