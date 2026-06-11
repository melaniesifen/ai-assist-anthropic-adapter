from __future__ import annotations

import json
import unittest

TEST_CREDENTIAL = "sk-ant-test-redacted"
TEST_MODEL = "test-anthropic-model"
TEST_MESSAGES = [{"role": "user", "content": "raw prompt stays out of logs"}]


class FakeClient:
    def __init__(self, *, validate_credential=None, generate=None, stream=None) -> None:
        self._validate_credential = validate_credential
        self._generate = generate
        self._stream = stream
        self.validate_calls = 0
        self.generate_calls = 0
        self.stream_calls = 0

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
        self.stream_calls += 1
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
