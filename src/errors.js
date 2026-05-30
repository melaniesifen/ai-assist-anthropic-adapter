import { ERROR_CATEGORIES, ERROR_CODES, PROVIDER } from "./constants.js";

const QUOTA_CODES = new Set(["insufficient_quota", "quota_exceeded", "billing_error", "credit_balance_too_low"]);
const INVALID_CREDENTIAL_CODES = new Set(["invalid_api_key", "invalid_credential", "authentication_error", "permission_error"]);
const POLICY_CODES = new Set(["content_policy_violation", "policy_violation", "safety_violation"]);
const CONTEXT_CODES = new Set(["context_length_exceeded", "context_too_large", "request_too_large"]);

export class ProviderAdapterError extends Error {
  constructor(normalizedError) {
    super(normalizedError.safeMessage);
    this.name = "ProviderAdapterError";
    this.normalizedError = normalizedError;
  }
}

export function validationError(code, safeMessage) {
  return Object.freeze({
    provider: PROVIDER,
    category: ERROR_CATEGORIES.VALIDATION,
    code,
    retryable: false,
    safeMessage
  });
}

export function invalidCredentialError() {
  return Object.freeze({
    provider: PROVIDER,
    category: ERROR_CATEGORIES.AUTHENTICATION,
    code: ERROR_CODES.INVALID_CREDENTIAL,
    retryable: false,
    safeMessage: "Provider credential is invalid or expired."
  });
}

export function clientConfigurationError() {
  return Object.freeze({
    provider: PROVIDER,
    category: ERROR_CATEGORIES.INTERNAL,
    code: ERROR_CODES.ADAPTER_CLIENT_INVALID,
    retryable: false,
    safeMessage: "Provider adapter client is not configured correctly."
  });
}

export function mapProviderError(error) {
  const statusCode = Number(error?.statusCode ?? error?.status ?? error?.response?.status);
  const providerCode = String(error?.code ?? error?.type ?? error?.error?.code ?? error?.error?.type ?? "").toLowerCase();
  const providerType = String(error?.type ?? error?.error?.type ?? "").toLowerCase();
  const providerSignal = providerCode || providerType;

  if (statusCode === 401 || statusCode === 403 || INVALID_CREDENTIAL_CODES.has(providerSignal)) {
    return normalized(ERROR_CATEGORIES.AUTHENTICATION, ERROR_CODES.INVALID_CREDENTIAL, false, "Provider credential is invalid or expired.", statusCode, providerSignal);
  }

  if (statusCode === 429 && QUOTA_CODES.has(providerSignal)) {
    return normalized(ERROR_CATEGORIES.PROVIDER_QUOTA, ERROR_CODES.PROVIDER_QUOTA_EXCEEDED, false, "Provider quota is exhausted.", statusCode, providerSignal);
  }

  if (statusCode === 429) {
    return normalized(ERROR_CATEGORIES.RATE_LIMITED, ERROR_CODES.PROVIDER_RATE_LIMITED, true, "Provider rate limit was reached.", statusCode, providerSignal);
  }

  if (POLICY_CODES.has(providerSignal)) {
    return normalized(ERROR_CATEGORIES.POLICY, ERROR_CODES.POLICY_BLOCKED, false, "Provider policy blocked the request.", statusCode, providerSignal);
  }

  if (CONTEXT_CODES.has(providerSignal)) {
    return normalized(ERROR_CATEGORIES.VALIDATION, ERROR_CODES.CONTEXT_TOO_LARGE, false, "Request context is too large for the provider.", statusCode, providerSignal);
  }

  if (statusCode === 400) {
    return normalized(ERROR_CATEGORIES.VALIDATION, ERROR_CODES.PROVIDER_VALIDATION_ERROR, false, "Provider rejected the request shape.", statusCode, providerSignal);
  }

  if ([408, 500, 502, 503, 504, 529].includes(statusCode)) {
    return normalized(ERROR_CATEGORIES.DEPENDENCY, ERROR_CODES.PROVIDER_UNAVAILABLE, true, "Provider is temporarily unavailable.", statusCode, providerSignal);
  }

  return normalized(ERROR_CATEGORIES.DEPENDENCY, ERROR_CODES.UNKNOWN_PROVIDER_ERROR, false, "Provider request failed.", statusCode, providerSignal);
}

function normalized(category, code, retryable, safeMessage, statusCode, providerSignal) {
  return Object.freeze({
    provider: PROVIDER,
    category,
    code,
    retryable,
    safeMessage,
    providerStatusCode: Number.isFinite(statusCode) ? statusCode : null,
    providerErrorSignal: providerSignal || null
  });
}
