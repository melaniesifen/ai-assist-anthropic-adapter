from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from typing import Any

from .constants import CAPABILITIES, ERROR_CODES, PROVIDER, STREAM_EVENT_TYPES
from .errors import (
    client_configuration_error,
    invalid_credential_error,
    map_provider_error,
    validation_error,
)
from .logging import SafeLogger
from .usage import normalize_usage

SUPPORTED_MESSAGE_ROLES = frozenset({"system", "user", "assistant"})


@dataclass(frozen=True)
class AnthropicAdapter:
    client: Any
    logger: Any

    def __post_init__(self) -> None:
        _assert_client(self.client)

    @property
    def provider(self) -> str:
        return PROVIDER

    def get_capabilities(self) -> dict[str, Any]:
        return CAPABILITIES.copy()

    async def validate_credential(self, request: dict[str, Any] | None = None) -> dict[str, Any]:
        request, request_shape_error = _coerce_request(request)
        metadata = _build_log_metadata("validateCredential", request)
        credential_error = request_shape_error or _validate_credential_value(request.get("credential"))
        if credential_error:
            self.logger.warn({**metadata, "errorCategory": credential_error["category"], "errorCode": credential_error["code"]})
            return _credential_validation_result(False, "invalid", credential_error)

        self.logger.info({**metadata, "dependencyStatus": "attempt"})
        try:
            result = await _maybe_await(self.client.validate_credential({
                "provider": PROVIDER,
                "credential": request.get("credential"),
            }))
            if not isinstance(result, dict) or result.get("valid") is not True:
                normalized_error = map_provider_error(result.get("error")) if isinstance(result, dict) and result.get("error") else invalid_credential_error()
                self.logger.warn({**metadata, "errorCategory": normalized_error["category"], "errorCode": normalized_error["code"]})
                status = result.get("status", "rejected") if isinstance(result, dict) else "rejected"
                return _credential_validation_result(False, status, normalized_error, result if isinstance(result, dict) else {})
            return _credential_validation_result(True, result.get("status", "valid"), None, result)
        except Exception as exc:
            normalized_error = map_provider_error(exc)
            self.logger.warn({**metadata, "errorCategory": normalized_error["category"], "errorCode": normalized_error["code"]})
            return _credential_validation_result(False, "rejected", normalized_error)

    async def generate(self, request: dict[str, Any] | None = None) -> dict[str, Any]:
        request, request_shape_error = _coerce_request(request)
        metadata = _build_log_metadata("generate", request)
        request_error = request_shape_error or _validate_generate_request(request)
        if request_error:
            self.logger.warn({**metadata, "errorCategory": request_error["category"], "errorCode": request_error["code"]})
            return _generate_error_result(request.get("model"), request_error)

        self.logger.info({**metadata, "dependencyStatus": "attempt"})
        try:
            raw = await _maybe_await(self.client.generate(_to_anthropic_request(request, stream=False)))
            result = _normalize_generate_result(raw if isinstance(raw, dict) else {}, request["model"])
            self.logger.info({**metadata, "dependencyStatus": "ok", "tokenUsage": result["usage"]})
            return result
        except Exception as exc:
            normalized_error = map_provider_error(exc)
            self.logger.warn({**metadata, "errorCategory": normalized_error["category"], "errorCode": normalized_error["code"]})
            return _generate_error_result(request.get("model"), normalized_error)

    async def stream(self, request: dict[str, Any] | None = None) -> AsyncIterator[dict[str, Any]]:
        request, request_shape_error = _coerce_request(request)
        metadata = _build_log_metadata("stream", request)
        request_error = request_shape_error or _validate_generate_request(request)
        if request_error:
            self.logger.warn({**metadata, "errorCategory": request_error["category"], "errorCode": request_error["code"]})
            yield _stream_error_event(request.get("model"), request_error)
            return

        self.logger.info({**metadata, "dependencyStatus": "attempt"})
        try:
            final_metadata: dict[str, Any] = {}
            stream_result = self.client.stream(_to_anthropic_request(request, stream=True))
            stream_iterable = await _maybe_await(stream_result)
            async for raw_event in _aiter(stream_iterable):
                final_metadata = _update_final_metadata(final_metadata, raw_event)
                normalized = _normalize_stream_event(raw_event, request["model"], final_metadata)
                if normalized:
                    yield normalized
        except Exception as exc:
            normalized_error = map_provider_error(exc)
            self.logger.warn({**metadata, "errorCategory": normalized_error["category"], "errorCode": normalized_error["code"]})
            yield _stream_error_event(request.get("model"), normalized_error)


def create_anthropic_adapter(*, client: Any, logger: Any | None = None) -> AnthropicAdapter:
    return AnthropicAdapter(client=client, logger=logger or SafeLogger())


def _assert_client(client: Any) -> None:
    required = ("validate_credential", "generate", "stream")
    if client is None or any(not callable(getattr(client, method, None)) for method in required):
        raise TypeError(client_configuration_error()["safeMessage"])


def _coerce_request(request: Any) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if request is None:
        return {}, None
    if not isinstance(request, dict):
        return {}, validation_error(ERROR_CODES["PROVIDER_VALIDATION_ERROR"], "Provider request must be an object.")
    return request, None


def _validate_credential_value(credential: Any) -> dict[str, Any] | None:
    if not isinstance(credential, str) or not credential.strip():
        return validation_error(ERROR_CODES["MISSING_CREDENTIAL"], "Provider credential is required.")
    return None


def _validate_generate_request(request: dict[str, Any]) -> dict[str, Any] | None:
    return (
        _validate_credential_value(request.get("credential"))
        or _validate_model(request.get("model"))
        or _validate_messages(request.get("messages"))
        or _validate_generation_parameters(request)
    )


def _validate_model(model: Any) -> dict[str, Any] | None:
    if not isinstance(model, str) or not model.strip():
        return validation_error(ERROR_CODES["MISSING_MODEL"], "Provider model is required.")
    return None


def _validate_messages(messages: Any) -> dict[str, Any] | None:
    if not isinstance(messages, list) or len(messages) == 0:
        return validation_error(ERROR_CODES["MISSING_MESSAGES"], "At least one message is required.")

    for message in messages:
        if not isinstance(message, dict) or message.get("role") not in SUPPORTED_MESSAGE_ROLES:
            return validation_error(ERROR_CODES["INVALID_MESSAGES"], "Messages must use supported roles.")
        if not _is_supported_content(message.get("content")):
            return validation_error(ERROR_CODES["INVALID_MESSAGES"], "Message content is required.")
    return None


def _is_supported_content(content: Any) -> bool:
    if isinstance(content, str):
        return bool(content.strip())
    if not isinstance(content, list) or len(content) == 0:
        return False
    return all(
        isinstance(part, dict)
        and part.get("type") == "text"
        and isinstance(part.get("text"), str)
        and bool(part["text"].strip())
        for part in content
    )


def _validate_generation_parameters(request: dict[str, Any]) -> dict[str, Any] | None:
    max_output_tokens = request.get("maxOutputTokens")
    if max_output_tokens is not None and (isinstance(max_output_tokens, bool) or not isinstance(max_output_tokens, int) or max_output_tokens <= 0):
        return validation_error(ERROR_CODES["PROVIDER_VALIDATION_ERROR"], "maxOutputTokens must be a positive integer.")

    temperature = request.get("temperature")
    if temperature is not None and (isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or temperature < 0 or temperature > 1):
        return validation_error(ERROR_CODES["PROVIDER_VALIDATION_ERROR"], "temperature must be a number between 0 and 1.")

    return None


def _build_log_metadata(operation: str, request: dict[str, Any]) -> dict[str, Any]:
    return {
        "service": "ai-assist-anthropic-adapter",
        "operation": operation,
        "requestId": request.get("requestId"),
        "correlationId": request.get("correlationId"),
        "tenantId": request.get("tenantId"),
        "userId": request.get("userId"),
        "sessionId": request.get("sessionId"),
        "provider": PROVIDER,
        "model": request.get("model"),
    }


def _to_anthropic_request(request: dict[str, Any], *, stream: bool) -> dict[str, Any]:
    return {
        "provider": PROVIDER,
        "credential": request["credential"],
        "model": request["model"],
        "messages": request["messages"],
        "temperature": request.get("temperature"),
        "max_tokens": request.get("maxOutputTokens"),
        "stream": stream,
        "requestId": request.get("requestId"),
        "correlationId": request.get("correlationId"),
    }


def _credential_validation_result(valid: bool, status: str, error: dict[str, Any] | None, raw: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = raw or {}
    return {
        "provider": PROVIDER,
        "valid": valid,
        "status": status,
        "fingerprint": raw.get("fingerprint"),
        "checkedAt": raw.get("checkedAt"),
        "error": error,
    }


def _normalize_generate_result(raw: dict[str, Any], requested_model: str) -> dict[str, Any]:
    content = raw.get("content")
    if isinstance(content, list):
        text = "".join(part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str))
    else:
        message = raw.get("message") if isinstance(raw.get("message"), dict) else {}
        text = raw.get("output_text") or message.get("content") or raw.get("content") or ""

    return {
        "provider": PROVIDER,
        "ok": True,
        "model": raw.get("model") or requested_model,
        "message": {
            "role": "assistant",
            "content": str(text),
        },
        "finishReason": raw.get("stop_reason") or raw.get("finish_reason"),
        "usage": normalize_usage(raw.get("usage")),
    }


def _generate_error_result(model: Any, error: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": PROVIDER,
        "ok": False,
        "model": model,
        "error": error,
    }


def _update_final_metadata(current: dict[str, Any], raw_event: Any) -> dict[str, Any]:
    if not isinstance(raw_event, dict):
        return current

    usage = current.get("usage")
    if raw_event.get("type") == "message_start":
        message = raw_event.get("message") if isinstance(raw_event.get("message"), dict) else {}
        usage = _merge_usage(usage, message.get("usage"))
        return {**current, "usage": usage} if usage is not None else current

    if raw_event.get("type") == "message_delta":
        delta = raw_event.get("delta") if isinstance(raw_event.get("delta"), dict) else {}
        usage = _merge_usage(usage, raw_event.get("usage"))
        return {
            "finishReason": delta.get("stop_reason") or current.get("finishReason"),
            "usage": usage,
        }

    return current


def _merge_usage(current: Any, incoming: Any) -> dict[str, int] | None:
    if not isinstance(current, dict) and not isinstance(incoming, dict):
        return None
    current_usage = normalize_usage(current if isinstance(current, dict) else {})
    incoming_usage = normalize_usage(incoming if isinstance(incoming, dict) else {})
    merged = {
        "inputTokens": incoming_usage["inputTokens"] if _has_any_usage_field(incoming, "inputTokens", "input_tokens") else current_usage["inputTokens"],
        "outputTokens": incoming_usage["outputTokens"] if _has_any_usage_field(incoming, "outputTokens", "output_tokens") else current_usage["outputTokens"],
        "totalTokens": 0,
    }
    merged["totalTokens"] = incoming_usage["totalTokens"] if _has_any_usage_field(incoming, "totalTokens", "total_tokens") else merged["inputTokens"] + merged["outputTokens"]
    return merged


def _has_any_usage_field(value: Any, *field_names: str) -> bool:
    return isinstance(value, dict) and any(field in value for field in field_names)


def _normalize_stream_event(raw_event: Any, requested_model: str, final_metadata: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(raw_event, dict):
        return None

    delta = _first_string(
        _nested(raw_event, "delta", "text"),
        raw_event.get("text"),
        _nested(raw_event, "content_block", "text"),
    )
    if delta:
        return {
            "type": STREAM_EVENT_TYPES["DELTA"],
            "provider": PROVIDER,
            "model": raw_event.get("model") or requested_model,
            "delta": delta,
        }

    completed = raw_event.get("type") == "message_stop" or raw_event.get("done") is True or bool(raw_event.get("stop_reason"))
    if completed:
        message = raw_event.get("message") if isinstance(raw_event.get("message"), dict) else raw_event
        return {
            "type": STREAM_EVENT_TYPES["FINAL"],
            "provider": PROVIDER,
            "model": message.get("model") or requested_model,
            "finishReason": message.get("stop_reason") or message.get("finish_reason") or final_metadata.get("finishReason"),
            "usage": normalize_usage(message.get("usage") or final_metadata.get("usage")),
        }

    return None


def _stream_error_event(model: Any, error: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": STREAM_EVENT_TYPES["ERROR"],
        "provider": PROVIDER,
        "model": model,
        "error": error,
    }


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _aiter(iterable: Any) -> AsyncIterator[Any]:
    if hasattr(iterable, "__aiter__"):
        async for item in iterable:
            yield item
        return

    if isinstance(iterable, Iterable):
        for item in iterable:
            yield item
        return

    raise TypeError("Injected client stream must return an iterable.")


def _first_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return None


def _nested(value: dict[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current
