from __future__ import annotations

import unittest

from ai_assist_anthropic_adapter import (
    ERROR_CATEGORIES,
    ERROR_CODES,
    PROVIDER,
    create_anthropic_adapter,
)

from common import (
    TEST_CREDENTIAL,
    TEST_MESSAGES,
    TEST_MODEL,
    CaptureLogger,
    FakeClient,
    ProviderError,
    assert_no_forbidden_log_material,
)


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

    async def test_generate_maps_provider_configuration_error_without_raw_error_leakage(self) -> None:
        logger = CaptureLogger()

        async def generate(_: dict) -> dict:
            raise ProviderError(type="configuration_error", message="raw provider config references secret material")

        adapter = create_anthropic_adapter(client=FakeClient(generate=generate), logger=logger)

        result = await adapter.generate({
            "providerAccess": {"source": "platform", "reference": "secret-ref:anthropic-default"},
            "model": TEST_MODEL,
            "messages": TEST_MESSAGES,
        })

        self.assertIs(result["ok"], False)
        self.assertEqual(result["error"]["category"], ERROR_CATEGORIES["INTERNAL"])
        self.assertEqual(result["error"]["code"], ERROR_CODES["ADAPTER_CLIENT_INVALID"])
        self.assertNotIn("raw provider", result["error"]["safeMessage"])
        assert_no_forbidden_log_material(self, logger.entries)

    async def test_generate_succeeds_with_default_safe_logger_and_usage_metadata(self) -> None:
        async def generate(_: dict) -> dict:
            return {
                "content": [{"type": "text", "text": "normalized answer"}],
                "usage": {"input_tokens": 1, "output_tokens": 2},
            }

        adapter = create_anthropic_adapter(client=FakeClient(generate=generate))

        result = await adapter.generate({
            "credential": TEST_CREDENTIAL,
            "model": TEST_MODEL,
            "messages": TEST_MESSAGES,
        })

        self.assertIs(result["ok"], True)
        self.assertEqual(result["usage"], {"inputTokens": 1, "outputTokens": 2, "totalTokens": 3})

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
        logger = CaptureLogger()

        async def stream(_: dict):
            yield {"type": "content_block_delta", "delta": {"text": "hel"}}
            yield {"text": "lo"}
            yield {"type": "message_stop", "message": {"usage": {"input_tokens": 2, "output_tokens": 1}, "stop_reason": "end_turn"}}

        adapter = create_anthropic_adapter(client=FakeClient(stream=stream), logger=logger)

        events = [event async for event in adapter.stream({"credential": TEST_CREDENTIAL, "model": TEST_MODEL, "messages": TEST_MESSAGES})]

        self.assertEqual([event["type"] for event in events], ["assistant.delta", "assistant.delta", "assistant.final"])
        self.assertEqual(events[0]["delta"], "hel")
        self.assertEqual(events[0]["provider"], PROVIDER)
        self.assertEqual(events[0]["model"], TEST_MODEL)
        self.assertEqual(events[2]["provider"], PROVIDER)
        self.assertEqual(events[2]["model"], TEST_MODEL)
        self.assertEqual(events[2]["usage"], {"inputTokens": 2, "outputTokens": 1, "totalTokens": 3})
        assert_no_forbidden_log_material(self, logger.entries)

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

    async def test_stream_returns_safe_error_event_for_provider_failure(self) -> None:
        logger = CaptureLogger()

        async def stream(_: dict):
            raise ProviderError(statusCode=503, type="api_error", message="raw provider message")
            yield

        adapter = create_anthropic_adapter(client=FakeClient(stream=stream), logger=logger)

        events = [event async for event in adapter.stream({"credential": TEST_CREDENTIAL, "model": TEST_MODEL, "messages": TEST_MESSAGES})]

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "error")
        self.assertEqual(events[0]["provider"], PROVIDER)
        self.assertEqual(events[0]["model"], TEST_MODEL)
        self.assertEqual(events[0]["error"]["category"], ERROR_CATEGORIES["DEPENDENCY"])
        self.assertEqual(events[0]["error"]["code"], ERROR_CODES["PROVIDER_UNAVAILABLE"])
        self.assertEqual(events[0]["error"]["message"], "Provider is temporarily unavailable.")
        self.assertEqual(events[0]["error"]["dependencyStatus"], "failed")
        self.assertEqual(set(events[0]["error"].keys()), {"category", "code", "message", "dependencyStatus"})
        assert_no_forbidden_log_material(self, logger.entries)

    async def test_stream_returns_error_when_provider_stream_has_no_terminal_event(self) -> None:
        adapter = create_anthropic_adapter(client=FakeClient(stream=lambda _: iter(())), logger=CaptureLogger())

        events = [event async for event in adapter.stream({"credential": TEST_CREDENTIAL, "model": TEST_MODEL, "messages": TEST_MESSAGES})]

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "error")
        self.assertEqual(events[0]["error"]["category"], ERROR_CATEGORIES["DEPENDENCY"])
        self.assertEqual(events[0]["error"]["code"], ERROR_CODES["UNKNOWN_PROVIDER_ERROR"])

    async def test_stream_returns_error_when_provider_stream_events_are_unknown(self) -> None:
        async def stream(_: dict):
            yield {"type": "provider.event.without_delta_or_finish"}

        adapter = create_anthropic_adapter(client=FakeClient(stream=stream), logger=CaptureLogger())

        events = [event async for event in adapter.stream({"credential": TEST_CREDENTIAL, "model": TEST_MODEL, "messages": TEST_MESSAGES})]

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "error")
        self.assertEqual(events[0]["error"]["category"], ERROR_CATEGORIES["DEPENDENCY"])
        self.assertEqual(events[0]["error"]["code"], ERROR_CODES["UNKNOWN_PROVIDER_ERROR"])
