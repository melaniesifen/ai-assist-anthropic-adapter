from __future__ import annotations

from typing import Any


def normalize_usage(raw_usage: dict[str, Any] | None = None) -> dict[str, int]:
    raw_usage = raw_usage or {}
    input_tokens = _number_or_zero(raw_usage.get("inputTokens", raw_usage.get("input_tokens")))
    output_tokens = _number_or_zero(raw_usage.get("outputTokens", raw_usage.get("output_tokens")))
    total_tokens = _number_or_zero(raw_usage.get("totalTokens", raw_usage.get("total_tokens", input_tokens + output_tokens)))

    return {
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "totalTokens": total_tokens,
    }


def _number_or_zero(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return 0
    return int(value)
