from __future__ import annotations

import json
import unittest

from ai_assist_anthropic_adapter import (
    ERROR_CATEGORIES,
    ERROR_CODES,
    PROVIDER,
    create_anthropic_adapter,
    map_provider_error,
    sanitize_log_fields,
)

TEST_CREDENTIAL = "sk-ant-test-redacted"
TEST_MODEL = "test-anthropic-model"
TEST_MESSAGES = [{"role": "user", "content": "raw prompt stays out of logs"}]


class AnthropicAdapterTest(unittest.IsolatedAsyncioTestCase):
    async def test_exposes_provider_capability_metadata_without_requiring_default_model(self) -> None:
        adapter = create_anthropic_adapter(client=FakeClient())

        self.assertEqual(adapter.provider, PROVIDER)
        self.assertEqual(adapter.get_capabilities()["provider"], PROVIDER)
        self.assertIs(adapter.get_capabilities()["supportsStreaming"], True)
        self.assertIs(adapter.get_capabilities()["supportsToolCalls"], False)
        self.assertIs(adapter.get_capabilities()["supportsStructuredOutput"], False)
        self.assertIsNone(adapter.get_capabilities()["defaultModel"])

    async def test_validate_credential_rejects_missing_credentials_without_calling_injected_client(self) -> None:
        client = FakeClient()
        adapter = create_anthropic_adapter(client=client, logger=CaptureLogger())

        result = await adapter.validate_credential({"credential": "   ", "requestId": "req-1"})

        self.assertEqual(client.validate_calls, 0)
        self.assertIs(result["valid"], False)
        self.assertEqual(result["error"]["code"], ERROR_CODES["MISSING_CREDENTIAL"])

    async def test_validate_credential_normalizes_injected_provider_auth_failure(self) -> None:
        async def validate_credential(_: dict) -> dict:
            raise ProviderError(statusCode=401, type="authentication_error")

        adapter = create_anthropic_adapter(client=FakeClient(validate_credential=validate_credential), logger=CaptureLogger())

        result = await adapter.validate_credential({"credential": TEST_CREDENTIAL})

        self.assertIs(result["valid"], False)
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["error"]["code"], ERROR_CODES["INVALID_CREDENTIAL"])

    async def test_validate_credential_fails_closed_for_ambiguous_injected_client_results(self) -> None:
        async def validate_credential(_: dict) -> dict:
            return {}

        adapter = create_anthropic_adapter(client=FakeClient(validate_credential=validate_credential), logger=CaptureLogger())

        result = await adapter.validate_credential({"credential": TEST_CREDENTIAL})

        self.assertIs(result["valid"], False)
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["error"]["code"], ERROR_CODES["INVALID_CREDENTIAL"])

    async def test_generate_maps_provider_neutral_request_to_anthropic_style_injected_client_request(self) -> None:
        observed_request = None
        logger = CaptureLogger()

        async def generate(request: dict) -> dict:
            nonlocal observed_request
            observed_request = request
            return {
                "model": request["model"],
                "content": [{"type": "text", "text": "normalized answer"}],
                "usage": {"input_tokens": 7, "output_tokens": 3},
                "stop_reason": "end_turn",
            }

        adapter = create_anthropic_adapter(client=FakeClient(generate=generate), logger=logger)

        result = await adapter.generate({
            "credential": TEST_CREDENTIAL,
            "model": TEST_MODEL,
            "messages": TEST_MESSAGES,
            "maxOutputTokens": 128,
            "requestId": "req-2",
            "correlationId": "corr-2",
        })

        self.assertIs(result["ok"], True)
        self.assertEqual(result["message"]["content"], "normalized answer")
        self.assertEqual(result["usage"], {"inputTokens": 7, "outputTokens": 3, "totalTokens": 10})
        self.assertEqual(observed_request["max_tokens"], 128)
        self.assertIs(observed_request["stream"], False)
        self.assertIs(observed_request["messages"], TEST_MESSAGES)
        assert_no_forbidden_log_material(self, logger.entries)

    async def test_generate_returns_stable_rate_limit_error_mapping(self) -> None:
        async def generate(_: dict) -> dict:
            raise ProviderError(statusCode=429, type="rate_limit_error", message="raw provider message")

        adapter = create_anthropic_adapter(client=FakeClient(generate=generate), logger=CaptureLogger())

        result = await adapter.generate({
            "credential": TEST_CREDENTIAL,
            "model": TEST_MODEL,
            "messages": TEST_MESSAGES,
        })

        self.assertIs(result["ok"], False)
        self.assertEqual(result["error"]["code"], ERROR_CODES["PROVIDER_RATE_LIMITED"])
        self.assertEqual(result["error"]["safeMessage"], "Provider rate limit was reached.")

    async def test_generate_rejects_malformed_messages_and_parameters_before_calling_injected_client(self) -> None:
        client = FakeClient()
        adapter = create_anthropic_adapter(client=client, logger=CaptureLogger())

        invalid_message = await adapter.generate({
            "credential": TEST_CREDENTIAL,
            "model": TEST_MODEL,
            "messages": [{"role": "bogus", "content": "   "}],
        })
        invalid_tokens = await adapter.generate({
            "credential": TEST_CREDENTIAL,
            "model": TEST_MODEL,
            "messages": TEST_MESSAGES,
            "maxOutputTokens": -1,
        })
        invalid_temperature = await adapter.generate({
            "credential": TEST_CREDENTIAL,
            "model": TEST_MODEL,
            "messages": TEST_MESSAGES,
            "temperature": "hot",
        })
        invalid_bool_tokens = await adapter.generate({
            "credential": TEST_CREDENTIAL,
            "model": TEST_MODEL,
            "messages": TEST_MESSAGES,
            "maxOutputTokens": True,
        })

        self.assertEqual(client.generate_calls, 0)
        self.assertEqual(invalid_message["error"]["code"], ERROR_CODES["INVALID_MESSAGES"])
        self.assertEqual(invalid_tokens["error"]["code"], ERROR_CODES["PROVIDER_VALIDATION_ERROR"])
        self.assertEqual(invalid_temperature["error"]["code"], ERROR_CODES["PROVIDER_VALIDATION_ERROR"])
        self.assertEqual(invalid_bool_tokens["error"]["code"], ERROR_CODES["PROVIDER_VALIDATION_ERROR"])

    async def test_public_methods_reject_non_object_requests_without_calling_injected_client(self) -> None:
        client = FakeClient()
        adapter = create_anthropic_adapter(client=client, logger=CaptureLogger())

        credential_result = await adapter.validate_credential("bad-request")
        generate_result = await adapter.generate("bad-request")
        stream_events = [event async for event in adapter.stream("bad-request")]

        self.assertEqual(client.validate_calls, 0)
        self.assertEqual(client.generate_calls, 0)
        self.assertIs(credential_result["valid"], False)
        self.assertEqual(credential_result["error"]["code"], ERROR_CODES["PROVIDER_VALIDATION_ERROR"])
        self.assertIs(generate_result["ok"], False)
        self.assertEqual(generate_result["error"]["code"], ERROR_CODES["PROVIDER_VALIDATION_ERROR"])
        self.assertEqual(stream_events[0]["type"], "error")
        self.assertEqual(stream_events[0]["error"]["code"], ERROR_CODES["PROVIDER_VALIDATION_ERROR"])

    async def test_stream_normalizes_anthropic_delta_and_final_events(self) -> None:
        async def stream(_: dict):
            yield {"type": "content_block_delta", "delta": {"text": "hel"}}
            yield {"text": "lo"}
            yield {"type": "message_stop", "message": {"usage": {"input_tokens": 2, "output_tokens": 1}, "stop_reason": "end_turn"}}

        adapter = create_anthropic_adapter(client=FakeClient(stream=stream), logger=CaptureLogger())

        events = [event async for event in adapter.stream({"credential": TEST_CREDENTIAL, "model": TEST_MODEL, "messages": TEST_MESSAGES})]

        self.assertEqual([event["type"] for event in events], ["assistant.delta", "assistant.delta", "assistant.final"])
        self.assertEqual(events[0]["delta"], "hel")
        self.assertEqual(events[2]["usage"], {"inputTokens": 2, "outputTokens": 1, "totalTokens": 3})

    async def test_stream_preserves_anthropic_message_delta_final_metadata(self) -> None:
        async def stream(_: dict):
            yield {"type": "content_block_delta", "delta": {"text": "hello"}}
            yield {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"input_tokens": 4, "output_tokens": 2}}
            yield {"type": "message_stop"}

        adapter = create_anthropic_adapter(client=FakeClient(stream=stream), logger=CaptureLogger())

        events = [event async for event in adapter.stream({"credential": TEST_CREDENTIAL, "model": TEST_MODEL, "messages": TEST_MESSAGES})]

        self.assertEqual([event["type"] for event in events], ["assistant.delta", "assistant.final"])
        self.assertEqual(events[1]["finishReason"], "end_turn")
        self.assertEqual(events[1]["usage"], {"inputTokens": 4, "outputTokens": 2, "totalTokens": 6})

    async def test_stream_merges_message_start_and_message_delta_usage_metadata(self) -> None:
        async def stream(_: dict):
            yield {"type": "message_start", "message": {"usage": {"input_tokens": 9}}}
            yield {"type": "content_block_delta", "delta": {"text": "hello"}}
            yield {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 4}}
            yield {"type": "message_stop"}

        adapter = create_anthropic_adapter(client=FakeClient(stream=stream), logger=CaptureLogger())

        events = [event async for event in adapter.stream({"credential": TEST_CREDENTIAL, "model": TEST_MODEL, "messages": TEST_MESSAGES})]

        self.assertEqual(events[-1]["type"], "assistant.final")
        self.assertEqual(events[-1]["finishReason"], "end_turn")
        self.assertEqual(events[-1]["usage"], {"inputTokens": 9, "outputTokens": 4, "totalTokens": 13})


class ErrorMappingTest(unittest.TestCase):
    def test_maps_python_and_anthropic_error_shapes_to_stable_categories(self) -> None:
        rate_limited = map_provider_error(ProviderError(status_code=429, type="rate_limit_error"))
        unavailable = map_provider_error(ProviderError(response=Response(status_code=503)))
        overloaded = map_provider_error({"error": {"type": "overloaded_error"}})
        context_too_large = map_provider_error(ProviderError(status_code=413))

        self.assertEqual(rate_limited["category"], ERROR_CATEGORIES["RATE_LIMITED"])
        self.assertEqual(rate_limited["code"], ERROR_CODES["PROVIDER_RATE_LIMITED"])
        self.assertEqual(rate_limited["providerStatusCode"], 429)
        self.assertEqual(unavailable["category"], ERROR_CATEGORIES["DEPENDENCY"])
        self.assertEqual(unavailable["code"], ERROR_CODES["PROVIDER_UNAVAILABLE"])
        self.assertEqual(unavailable["providerStatusCode"], 503)
        self.assertEqual(overloaded["code"], ERROR_CODES["PROVIDER_UNAVAILABLE"])
        self.assertEqual(overloaded["providerErrorSignal"], "overloaded_error")
        self.assertEqual(context_too_large["code"], ERROR_CODES["CONTEXT_TOO_LARGE"])


class LoggingTest(unittest.TestCase):
    def test_sanitize_log_fields_rejects_secret_and_prompt_bearing_fields(self) -> None:
        with self.assertRaisesRegex(TypeError, "Forbidden log field"):
            sanitize_log_fields({"requestId": "req", "credential": TEST_CREDENTIAL})
        with self.assertRaisesRegex(TypeError, "Forbidden log field"):
            sanitize_log_fields({"requestId": "req", "nested": {"prompt": "do not log"}})

        self.assertEqual(sanitize_log_fields({"requestId": "req", "ignored": "value", "provider": PROVIDER}), {
            "requestId": "req",
            "provider": PROVIDER,
        })


class FakeClient:
    def __init__(self, *, validate_credential=None, generate=None, stream=None) -> None:
        self._validate_credential = validate_credential
        self._generate = generate
        self._stream = stream
        self.validate_calls = 0
        self.generate_calls = 0

    async def validate_credential(self, request: dict) -> dict:
        self.validate_calls += 1
        if self._validate_credential:
            return await self._validate_credential(request)
        return {"valid": True, "status": "valid", "fingerprint": "fp-test"}

    async def generate(self, request: dict) -> dict:
        self.generate_calls += 1
        if self._generate:
            return await self._generate(request)
        return {"content": [{"type": "text", "text": "ok"}], "usage": {}}

    def stream(self, request: dict):
        if self._stream:
            return self._stream(request)
        return empty_async_iter()


async def empty_async_iter():
    if False:
        yield None


class ProviderError(Exception):
    def __init__(self, **kwargs) -> None:
        super().__init__(kwargs.get("message", "provider error"))
        for key, value in kwargs.items():
            setattr(self, key, value)


class Response:
    def __init__(self, *, status_code: int) -> None:
        self.status_code = status_code


class CaptureLogger:
    def __init__(self) -> None:
        self.entries = []

    def info(self, fields: dict) -> None:
        self.entries.append(fields)

    def warn(self, fields: dict) -> None:
        self.entries.append(fields)

    def error(self, fields: dict) -> None:
        self.entries.append(fields)


def assert_no_forbidden_log_material(test_case: unittest.TestCase, entries: list[dict]) -> None:
    serialized = json.dumps(entries)
    test_case.assertNotIn(TEST_CREDENTIAL, serialized)
    test_case.assertNotIn("raw prompt stays out of logs", serialized)
    test_case.assertNotIn("normalized answer", serialized)


if __name__ == "__main__":
    unittest.main()
