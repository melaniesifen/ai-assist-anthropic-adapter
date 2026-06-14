from __future__ import annotations

import unittest

from ai_assist_anthropic_adapter import ERROR_CATEGORIES, ERROR_CODES, map_provider_error

from common import ProviderError, Response


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

    def test_maps_provider_error_category_matrix_for_orchestration(self) -> None:
        cases = [
            (ProviderError(statusCode=401, type="authentication_error"), ERROR_CATEGORIES["AUTHENTICATION"], ERROR_CODES["INVALID_CREDENTIAL"], False),
            (ProviderError(statusCode=429, type="insufficient_quota"), ERROR_CATEGORIES["PROVIDER_QUOTA"], ERROR_CODES["PROVIDER_QUOTA_EXCEEDED"], False),
            (ProviderError(statusCode=429, type="rate_limit_error"), ERROR_CATEGORIES["RATE_LIMITED"], ERROR_CODES["PROVIDER_RATE_LIMITED"], True),
            (ProviderError(statusCode=400, type="invalid_request_error"), ERROR_CATEGORIES["VALIDATION"], ERROR_CODES["PROVIDER_VALIDATION_ERROR"], False),
            (ProviderError(statusCode=413, type="request_too_large"), ERROR_CATEGORIES["VALIDATION"], ERROR_CODES["CONTEXT_TOO_LARGE"], False),
            (ProviderError(statusCode=529, type="overloaded_error"), ERROR_CATEGORIES["DEPENDENCY"], ERROR_CODES["PROVIDER_UNAVAILABLE"], True),
            (ProviderError(type="request_timeout"), ERROR_CATEGORIES["TIMEOUT"], ERROR_CODES["PROVIDER_UNAVAILABLE"], True),
            (ProviderError(type="content_policy_violation"), ERROR_CATEGORIES["POLICY"], ERROR_CODES["POLICY_BLOCKED"], False),
            (ProviderError(type="unexpected_error"), ERROR_CATEGORIES["DEPENDENCY"], ERROR_CODES["UNKNOWN_PROVIDER_ERROR"], False),
        ]

        for error, category, code, retryable in cases:
            with self.subTest(code=code):
                mapped = map_provider_error(error)
                self.assertEqual(mapped["category"], category)
                self.assertEqual(mapped["code"], code)
                self.assertIs(mapped["retryable"], retryable)
                self.assertNotIn("raw provider", mapped["safeMessage"])
