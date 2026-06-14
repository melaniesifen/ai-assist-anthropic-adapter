from __future__ import annotations

import unittest

from ai_assist_anthropic_adapter import ERROR_CODES, create_anthropic_adapter, provider_status
from common import CaptureLogger, FakeClient, TEST_MESSAGES, TEST_MODEL, assert_no_forbidden_log_material


class AnthropicProviderAccessTest(unittest.IsolatedAsyncioTestCase):
    async def test_generate_uses_platform_provider_access_without_user_credential(self) -> None:
        observed = {}
        logger = CaptureLogger()

        async def generate(request: dict) -> dict:
            observed.update(request)
            return {"content": [{"type": "text", "text": "normalized answer"}], "usage": {}}

        adapter = create_anthropic_adapter(client=FakeClient(generate=generate), logger=logger)

        result = await adapter.generate(
            {
                "providerAccess": {"source": "platform", "reference": "secret-ref:anthropic-default"},
                "model": TEST_MODEL,
                "messages": TEST_MESSAGES,
            }
        )

        self.assertTrue(result["ok"])
        self.assertNotIn("credential", observed)
        self.assertEqual(observed["providerAccess"], {"source": "platform", "reference": "secret-ref:anthropic-default"})
        assert_no_forbidden_log_material(self, logger.entries)

    async def test_stream_uses_optional_byo_access_when_explicitly_configured(self) -> None:
        observed = {}

        async def stream(request: dict):
            observed.update(request)
            yield {"type": "message_stop", "message": {"usage": {}, "stop_reason": "end_turn"}}

        adapter = create_anthropic_adapter(client=FakeClient(stream=stream), logger=CaptureLogger())

        events = [
            event
            async for event in adapter.stream(
                {
                    "providerAccess": {"source": "byo", "credential": "sk-ant-test-redacted", "secretRef": "secret_001"},
                    "model": TEST_MODEL,
                    "messages": TEST_MESSAGES,
                }
            )
        ]

        self.assertEqual(events[-1]["type"], "assistant.final")
        self.assertEqual(observed["credential"], "sk-ant-test-redacted")
        self.assertEqual(observed["providerAccess"], {"source": "byo", "secretRef": "secret_001"})

    async def test_generate_rejects_missing_provider_access_without_calling_client(self) -> None:
        client = FakeClient()
        adapter = create_anthropic_adapter(client=client, logger=CaptureLogger())

        result = await adapter.generate({"model": TEST_MODEL, "messages": TEST_MESSAGES})

        self.assertFalse(result["ok"])
        self.assertEqual(client.generate_calls, 0)
        self.assertEqual(result["error"]["code"], ERROR_CODES["MISSING_CREDENTIAL"])

    async def test_generate_rejects_missing_platform_secret_reference_without_calling_client(self) -> None:
        client = FakeClient()
        logger = CaptureLogger()
        adapter = create_anthropic_adapter(client=client, logger=logger)

        result = await adapter.generate({
            "providerAccess": {"source": "platform", "reference": "   "},
            "model": TEST_MODEL,
            "messages": TEST_MESSAGES,
        })

        self.assertFalse(result["ok"])
        self.assertEqual(client.generate_calls, 0)
        self.assertEqual(result["error"]["code"], ERROR_CODES["MISSING_CREDENTIAL"])
        self.assertEqual(result["error"]["safeMessage"], "Platform provider secret reference is required.")
        assert_no_forbidden_log_material(self, logger.entries)

    async def test_stream_rejects_missing_byo_secret_access_without_calling_client(self) -> None:
        client = FakeClient()
        adapter = create_anthropic_adapter(client=client, logger=CaptureLogger())

        events = [
            event
            async for event in adapter.stream(
                {
                    "providerAccess": {"source": "byo", "secretRef": "secret_001"},
                    "model": TEST_MODEL,
                    "messages": TEST_MESSAGES,
                }
            )
        ]

        self.assertEqual(client.stream_calls, 0)
        self.assertEqual(events[0]["type"], "error")
        self.assertEqual(events[0]["error"]["code"], ERROR_CODES["MISSING_CREDENTIAL"])

    async def test_generate_rejects_unsupported_provider_access_source_without_calling_client(self) -> None:
        client = FakeClient()
        adapter = create_anthropic_adapter(client=client, logger=CaptureLogger())

        result = await adapter.generate({
            "providerAccess": {"source": "ambient"},
            "model": TEST_MODEL,
            "messages": TEST_MESSAGES,
        })

        self.assertFalse(result["ok"])
        self.assertEqual(client.generate_calls, 0)
        self.assertEqual(result["error"]["code"], ERROR_CODES["PROVIDER_VALIDATION_ERROR"])

    def test_provider_status_can_report_deferred_anthropic_support_safely(self) -> None:
        status = provider_status(
            status="deferred",
            access_source="platform",
            configured=False,
            reason_code="PROVIDER_NOT_ENABLED",
            checked_at="2026-06-14T00:00:00Z",
        )

        self.assertEqual(status["provider"], "anthropic")
        self.assertEqual(status["status"], "deferred")
        self.assertEqual(status["accessSource"], "platform")
        self.assertFalse(status["configured"])
        self.assertNotIn("credential", status)
        self.assertNotIn("secret", status)


if __name__ == "__main__":
    unittest.main()
