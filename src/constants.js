export const PROVIDER = "anthropic";

export const ERROR_CATEGORIES = Object.freeze({
  AUTHENTICATION: "AUTHENTICATION",
  RATE_LIMITED: "RATE_LIMITED",
  VALIDATION: "VALIDATION",
  DEPENDENCY: "DEPENDENCY",
  PROVIDER_QUOTA: "PROVIDER_QUOTA",
  POLICY: "POLICY",
  INTERNAL: "INTERNAL"
});

export const ERROR_CODES = Object.freeze({
  INVALID_CREDENTIAL: "INVALID_CREDENTIAL",
  INVALID_MESSAGES: "INVALID_MESSAGES",
  MISSING_CREDENTIAL: "MISSING_CREDENTIAL",
  MISSING_MODEL: "MISSING_MODEL",
  MISSING_MESSAGES: "MISSING_MESSAGES",
  PROVIDER_RATE_LIMITED: "PROVIDER_RATE_LIMITED",
  PROVIDER_QUOTA_EXCEEDED: "PROVIDER_QUOTA_EXCEEDED",
  PROVIDER_UNAVAILABLE: "PROVIDER_UNAVAILABLE",
  POLICY_BLOCKED: "POLICY_BLOCKED",
  CONTEXT_TOO_LARGE: "CONTEXT_TOO_LARGE",
  PROVIDER_VALIDATION_ERROR: "PROVIDER_VALIDATION_ERROR",
  UNKNOWN_PROVIDER_ERROR: "UNKNOWN_PROVIDER_ERROR",
  ADAPTER_CLIENT_INVALID: "ADAPTER_CLIENT_INVALID"
});

export const STREAM_EVENT_TYPES = Object.freeze({
  DELTA: "assistant.delta",
  FINAL: "assistant.final",
  ERROR: "error"
});

export const CAPABILITIES = Object.freeze({
  provider: PROVIDER,
  displayName: "Anthropic",
  supportsStreaming: true,
  supportsJsonMode: false,
  supportsStructuredOutput: false,
  supportsToolCalls: false,
  supportsVision: false,
  supportedModalities: Object.freeze(["text"]),
  defaultModel: null,
  maxContextTokens: null,
  costMetadata: Object.freeze({
    currency: "USD",
    source: "provider-pricing",
    lastVerifiedAt: null
  })
});
