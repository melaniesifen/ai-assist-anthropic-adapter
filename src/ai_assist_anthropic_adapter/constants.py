from types import MappingProxyType

PROVIDER = "anthropic"

ERROR_CATEGORIES = MappingProxyType({
    "AUTHENTICATION": "AUTHENTICATION",
    "RATE_LIMITED": "RATE_LIMITED",
    "VALIDATION": "VALIDATION",
    "DEPENDENCY": "DEPENDENCY",
    "PROVIDER_QUOTA": "PROVIDER_QUOTA",
    "POLICY": "POLICY",
    "INTERNAL": "INTERNAL",
})

ERROR_CODES = MappingProxyType({
    "INVALID_CREDENTIAL": "INVALID_CREDENTIAL",
    "INVALID_MESSAGES": "INVALID_MESSAGES",
    "MISSING_CREDENTIAL": "MISSING_CREDENTIAL",
    "MISSING_MODEL": "MISSING_MODEL",
    "MISSING_MESSAGES": "MISSING_MESSAGES",
    "PROVIDER_RATE_LIMITED": "PROVIDER_RATE_LIMITED",
    "PROVIDER_QUOTA_EXCEEDED": "PROVIDER_QUOTA_EXCEEDED",
    "PROVIDER_UNAVAILABLE": "PROVIDER_UNAVAILABLE",
    "POLICY_BLOCKED": "POLICY_BLOCKED",
    "CONTEXT_TOO_LARGE": "CONTEXT_TOO_LARGE",
    "PROVIDER_VALIDATION_ERROR": "PROVIDER_VALIDATION_ERROR",
    "UNKNOWN_PROVIDER_ERROR": "UNKNOWN_PROVIDER_ERROR",
    "ADAPTER_CLIENT_INVALID": "ADAPTER_CLIENT_INVALID",
})

STREAM_EVENT_TYPES = MappingProxyType({
    "DELTA": "assistant.delta",
    "FINAL": "assistant.final",
    "ERROR": "error",
})

CAPABILITIES = {
    "provider": PROVIDER,
    "displayName": "Anthropic",
    "supportsStreaming": True,
    "supportsJsonMode": False,
    "supportsStructuredOutput": False,
    "supportsToolCalls": False,
    "supportsVision": False,
    "supportedModalities": ["text"],
    "defaultModel": None,
    "maxContextTokens": None,
    "costMetadata": {
        "currency": "USD",
        "source": "provider-pricing",
        "lastVerifiedAt": None,
    },
}
