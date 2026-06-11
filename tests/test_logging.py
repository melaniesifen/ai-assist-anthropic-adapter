from __future__ import annotations

import unittest

from ai_assist_anthropic_adapter import PROVIDER, sanitize_log_fields

from common import TEST_CREDENTIAL


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

    def test_sanitize_log_fields_allows_normalized_token_usage_metadata(self) -> None:
        self.assertEqual(sanitize_log_fields({
            "requestId": "req",
            "tokenUsage": {"inputTokens": 1, "outputTokens": 2, "totalTokens": 3},
        }), {
            "requestId": "req",
            "tokenUsage": {"inputTokens": 1, "outputTokens": 2, "totalTokens": 3},
        })
