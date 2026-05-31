from __future__ import annotations

from typing import Any

from .constants import ERROR_CATEGORIES, ERROR_CODES, PROVIDER

QUOTA_CODES = frozenset({"insufficient_quota", "quota_exceeded", "billing_error", "credit_balance_too_low"})
INVALID_CREDENTIAL_CODES = frozenset({"invalid_api_key", "invalid_credential", "authentication_error", "permission_error"})
RATE_LIMIT_CODES = frozenset({"rate_limit_error"})
POLICY_CODES = frozenset({"content_policy_violation", "policy_violation", "safety_violation"})
CONTEXT_CODES = frozenset({"context_length_exceeded", "context_too_large", "request_too_large"})
UNAVAILABLE_CODES = frozenset({"api_error", "overloaded_error"})
UNAVAILABLE_STATUS_CODES = frozenset({408, 500, 502, 503, 504, 529})


class ProviderAdapterError(Exception):
    def __init__(self, normalized_error: dict[str, Any]) -> None:
        super().__init__(normalized_error["safeMessage"])
        self.normalized_error = normalized_error


def validation_error(code: str, safe_message: str) -> dict[str, Any]:
    return {
        "provider": PROVIDER,
        "category": ERROR_CATEGORIES["VALIDATION"],
        "code": code,
        "retryable": False,
        "safeMessage": safe_message,
    }


def invalid_credential_error() -> dict[str, Any]:
    return {
        "provider": PROVIDER,
        "category": ERROR_CATEGORIES["AUTHENTICATION"],
        "code": ERROR_CODES["INVALID_CREDENTIAL"],
        "retryable": False,
        "safeMessage": "Provider credential is invalid or expired.",
    }


def client_configuration_error() -> dict[str, Any]:
    return {
        "provider": PROVIDER,
        "category": ERROR_CATEGORIES["INTERNAL"],
        "code": ERROR_CODES["ADAPTER_CLIENT_INVALID"],
        "retryable": False,
        "safeMessage": "Provider adapter client is not configured correctly.",
    }


def map_provider_error(error: Any) -> dict[str, Any]:
    status_code = _status_code(error)
    provider_code = _lower_first(error, ("code",), ("type",), ("error", "code"), ("error", "type"))
    provider_type = _lower_first(error, ("type",), ("error", "type"))
    provider_signal = provider_code or provider_type

    if status_code in {401, 403} or provider_signal in INVALID_CREDENTIAL_CODES:
        return _normalized(ERROR_CATEGORIES["AUTHENTICATION"], ERROR_CODES["INVALID_CREDENTIAL"], False, "Provider credential is invalid or expired.", status_code, provider_signal)

    if status_code == 413 or provider_signal in CONTEXT_CODES:
        return _normalized(ERROR_CATEGORIES["VALIDATION"], ERROR_CODES["CONTEXT_TOO_LARGE"], False, "Request context is too large for the provider.", status_code, provider_signal)

    if status_code == 429 and provider_signal in QUOTA_CODES:
        return _normalized(ERROR_CATEGORIES["PROVIDER_QUOTA"], ERROR_CODES["PROVIDER_QUOTA_EXCEEDED"], False, "Provider quota is exhausted.", status_code, provider_signal)

    if status_code == 429 or provider_signal in RATE_LIMIT_CODES:
        return _normalized(ERROR_CATEGORIES["RATE_LIMITED"], ERROR_CODES["PROVIDER_RATE_LIMITED"], True, "Provider rate limit was reached.", status_code, provider_signal)

    if provider_signal in POLICY_CODES:
        return _normalized(ERROR_CATEGORIES["POLICY"], ERROR_CODES["POLICY_BLOCKED"], False, "Provider policy blocked the request.", status_code, provider_signal)

    if status_code == 400:
        return _normalized(ERROR_CATEGORIES["VALIDATION"], ERROR_CODES["PROVIDER_VALIDATION_ERROR"], False, "Provider rejected the request shape.", status_code, provider_signal)

    if status_code in UNAVAILABLE_STATUS_CODES or provider_signal in UNAVAILABLE_CODES:
        return _normalized(ERROR_CATEGORIES["DEPENDENCY"], ERROR_CODES["PROVIDER_UNAVAILABLE"], True, "Provider is temporarily unavailable.", status_code, provider_signal)

    return _normalized(ERROR_CATEGORIES["DEPENDENCY"], ERROR_CODES["UNKNOWN_PROVIDER_ERROR"], False, "Provider request failed.", status_code, provider_signal)


def _normalized(category: str, code: str, retryable: bool, safe_message: str, status_code: int | None, provider_signal: str | None) -> dict[str, Any]:
    return {
        "provider": PROVIDER,
        "category": category,
        "code": code,
        "retryable": retryable,
        "safeMessage": safe_message,
        "providerStatusCode": status_code,
        "providerErrorSignal": provider_signal or None,
    }


def _status_code(error: Any) -> int | None:
    raw = (
        _lookup(error, ("statusCode",))
        or _lookup(error, ("status_code",))
        or _lookup(error, ("status",))
        or _lookup(error, ("response", "status"))
        or _lookup(error, ("response", "status_code"))
    )
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _lower_first(error: Any, *paths: tuple[str, ...]) -> str:
    for path in paths:
        value = _lookup(error, path)
        if value:
            return str(value).lower()
    return ""


def _lookup(value: Any, path: tuple[str, ...]) -> Any:
    current = value
    for key in path:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            current = getattr(current, key, None)
        if current is None:
            return None
    return current
