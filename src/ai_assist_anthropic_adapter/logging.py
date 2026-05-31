from __future__ import annotations

import logging
import re
from typing import Any

from .usage import normalize_usage

ALLOWED_FIELDS = frozenset({
    "timestamp",
    "service",
    "environment",
    "tenantId",
    "userId",
    "sessionId",
    "requestId",
    "correlationId",
    "route",
    "operation",
    "statusCode",
    "durationMs",
    "errorCategory",
    "errorCode",
    "provider",
    "connector",
    "model",
    "tokenUsage",
    "rateLimitDecision",
    "dependencyStatus",
})

FORBIDDEN_FIELD_PATTERNS = tuple(re.compile(pattern, re.IGNORECASE) for pattern in (
    r"prompt",
    r"message",
    r"content",
    r"response",
    r"output",
    r"completion",
    r"selected.*text",
    r"document.*text",
    r"api.*key",
    r"credential",
    r"secret",
    r"authorization",
    r"cookie",
    r"bearer",
    r"oauth",
    r"access.*token",
    r"refresh.*token",
))


def sanitize_log_fields(fields: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(fields, dict):
        raise TypeError("Log fields must be an object.")

    _assert_no_forbidden_fields(fields)

    safe: dict[str, Any] = {}
    for key, value in fields.items():
        if key not in ALLOWED_FIELDS or value is None:
            continue
        safe[key] = normalize_usage(value) if key == "tokenUsage" else value
    return safe


class SafeLogger:
    def __init__(self, sink: logging.Logger | None = None) -> None:
        self._sink = sink or logging.getLogger("ai_assist_anthropic_adapter")

    def info(self, fields: dict[str, Any]) -> None:
        self._write(logging.INFO, fields)

    def warn(self, fields: dict[str, Any]) -> None:
        self._write(logging.WARNING, fields)

    def error(self, fields: dict[str, Any]) -> None:
        self._write(logging.ERROR, fields)

    def _write(self, level: int, fields: dict[str, Any]) -> None:
        self._sink.log(level, "adapter_event", extra={"metadata": sanitize_log_fields(fields)})


def _assert_no_forbidden_fields(value: Any, path: tuple[str, ...] = ()) -> None:
    if not isinstance(value, dict):
        return

    for key, nested in value.items():
        next_path = (*path, key)
        if any(pattern.search(key) for pattern in FORBIDDEN_FIELD_PATTERNS):
            raise TypeError(f"Forbidden log field: {'.'.join(next_path)}")
        _assert_no_forbidden_fields(nested, next_path)
