import { CAPABILITIES, ERROR_CODES, PROVIDER, STREAM_EVENT_TYPES } from "./constants.js";
import { clientConfigurationError, invalidCredentialError, mapProviderError, validationError } from "./errors.js";
import { createSafeLogger } from "./logging.js";
import { normalizeUsage } from "./usage.js";

export function createAnthropicAdapter({ client, logger = createSafeLogger() } = {}) {
  assertClient(client);

  return Object.freeze({
    provider: PROVIDER,

    getCapabilities() {
      return CAPABILITIES;
    },

    async validateCredential(request = {}) {
      const metadata = buildLogMetadata("validateCredential", request);
      const credentialError = validateCredentialValue(request.credential);
      if (credentialError) {
        logger.warn({ ...metadata, errorCategory: credentialError.category, errorCode: credentialError.code });
        return credentialValidationResult(false, "invalid", credentialError);
      }

      logger.info({ ...metadata, dependencyStatus: "attempt" });
      try {
        const result = await client.validateCredential({
          provider: PROVIDER,
          credential: request.credential
        });
        if (result?.valid !== true) {
          const normalizedError = result?.error ? mapProviderError(result.error) : invalidCredentialError();
          logger.warn({ ...metadata, errorCategory: normalizedError.category, errorCode: normalizedError.code });
          return credentialValidationResult(false, result?.status ?? "rejected", normalizedError, result);
        }
        return credentialValidationResult(true, result.status ?? "valid", null, result);
      } catch (error) {
        const normalizedError = mapProviderError(error);
        logger.warn({ ...metadata, errorCategory: normalizedError.category, errorCode: normalizedError.code });
        return credentialValidationResult(false, "rejected", normalizedError);
      }
    },

    async generate(request = {}) {
      const metadata = buildLogMetadata("generate", request);
      const requestError = validateGenerateRequest(request);
      if (requestError) {
        logger.warn({ ...metadata, errorCategory: requestError.category, errorCode: requestError.code });
        return generateErrorResult(request.model, requestError);
      }

      logger.info({ ...metadata, dependencyStatus: "attempt" });
      try {
        const raw = await client.generate(toAnthropicRequest(request, false));
        const result = normalizeGenerateResult(raw, request.model);
        logger.info({ ...metadata, dependencyStatus: "ok", tokenUsage: result.usage });
        return result;
      } catch (error) {
        const normalizedError = mapProviderError(error);
        logger.warn({ ...metadata, errorCategory: normalizedError.category, errorCode: normalizedError.code });
        return generateErrorResult(request.model, normalizedError);
      }
    },

    async *stream(request = {}) {
      const metadata = buildLogMetadata("stream", request);
      const requestError = validateGenerateRequest(request);
      if (requestError) {
        logger.warn({ ...metadata, errorCategory: requestError.category, errorCode: requestError.code });
        yield streamErrorEvent(request.model, requestError);
        return;
      }

      logger.info({ ...metadata, dependencyStatus: "attempt" });
      try {
        let finalMetadata = {};
        for await (const rawEvent of client.stream(toAnthropicRequest(request, true))) {
          finalMetadata = updateFinalMetadata(finalMetadata, rawEvent);
          const normalized = normalizeStreamEvent(rawEvent, request.model, finalMetadata);
          if (normalized) {
            yield normalized;
          }
        }
      } catch (error) {
        const normalizedError = mapProviderError(error);
        logger.warn({ ...metadata, errorCategory: normalizedError.category, errorCode: normalizedError.code });
        yield streamErrorEvent(request.model, normalizedError);
      }
    }
  });
}

function assertClient(client) {
  if (!client || typeof client.validateCredential !== "function" || typeof client.generate !== "function" || typeof client.stream !== "function") {
    throw new TypeError(clientConfigurationError().safeMessage);
  }
}

function validateCredentialValue(credential) {
  if (typeof credential !== "string" || credential.trim().length === 0) {
    return validationError(ERROR_CODES.MISSING_CREDENTIAL, "Provider credential is required.");
  }
  return null;
}

function validateGenerateRequest(request) {
  return validateCredentialValue(request.credential)
    ?? (typeof request.model !== "string" || request.model.trim().length === 0
      ? validationError(ERROR_CODES.MISSING_MODEL, "Provider model is required.")
      : null)
    ?? validateMessages(request.messages)
    ?? validateGenerationParameters(request);
}

const SUPPORTED_MESSAGE_ROLES = new Set(["system", "user", "assistant"]);

function validateMessages(messages) {
  if (!Array.isArray(messages) || messages.length === 0) {
    return validationError(ERROR_CODES.MISSING_MESSAGES, "At least one message is required.");
  }

  for (const message of messages) {
    if (!message || typeof message !== "object" || !SUPPORTED_MESSAGE_ROLES.has(message.role)) {
      return validationError(ERROR_CODES.INVALID_MESSAGES, "Messages must use supported roles.");
    }

    if (!isSupportedContent(message.content)) {
      return validationError(ERROR_CODES.INVALID_MESSAGES, "Message content is required.");
    }
  }

  return null;
}

function isSupportedContent(content) {
  if (typeof content === "string") {
    return content.trim().length > 0;
  }

  return Array.isArray(content)
    && content.length > 0
    && content.every((part) => part
      && typeof part === "object"
      && part.type === "text"
      && typeof part.text === "string"
      && part.text.trim().length > 0);
}

function validateGenerationParameters(request) {
  if (request.maxOutputTokens !== undefined && (!Number.isInteger(request.maxOutputTokens) || request.maxOutputTokens <= 0)) {
    return validationError(ERROR_CODES.PROVIDER_VALIDATION_ERROR, "maxOutputTokens must be a positive integer.");
  }

  if (request.temperature !== undefined && (typeof request.temperature !== "number" || request.temperature < 0 || request.temperature > 1)) {
    return validationError(ERROR_CODES.PROVIDER_VALIDATION_ERROR, "temperature must be a number between 0 and 1.");
  }

  return null;
}

function buildLogMetadata(operation, request) {
  return {
    service: "ai-assist-anthropic-adapter",
    operation,
    requestId: request.requestId,
    correlationId: request.correlationId,
    tenantId: request.tenantId,
    userId: request.userId,
    sessionId: request.sessionId,
    provider: PROVIDER,
    model: request.model
  };
}

function toAnthropicRequest(request, stream) {
  return {
    provider: PROVIDER,
    credential: request.credential,
    model: request.model,
    messages: request.messages,
    temperature: request.temperature,
    max_tokens: request.maxOutputTokens,
    stream,
    requestId: request.requestId,
    correlationId: request.correlationId
  };
}

function credentialValidationResult(valid, status, error, raw = {}) {
  return Object.freeze({
    provider: PROVIDER,
    valid,
    status,
    fingerprint: raw?.fingerprint ?? null,
    checkedAt: raw?.checkedAt ?? null,
    error
  });
}

function normalizeGenerateResult(raw, requestedModel) {
  const content = raw?.content;
  const text = Array.isArray(content)
    ? content.filter((part) => part?.type === "text" && typeof part.text === "string").map((part) => part.text).join("")
    : raw?.output_text ?? raw?.message?.content ?? raw?.content ?? "";

  return Object.freeze({
    provider: PROVIDER,
    ok: true,
    model: raw?.model ?? requestedModel,
    message: Object.freeze({
      role: "assistant",
      content: String(text)
    }),
    finishReason: raw?.stop_reason ?? raw?.finish_reason ?? null,
    usage: normalizeUsage(raw?.usage)
  });
}

function generateErrorResult(model, error) {
  return Object.freeze({
    provider: PROVIDER,
    ok: false,
    model: model ?? null,
    error
  });
}

function updateFinalMetadata(current, rawEvent) {
  if (rawEvent?.type !== "message_delta") {
    return current;
  }

  return {
    finishReason: rawEvent.delta?.stop_reason ?? current.finishReason,
    usage: rawEvent.usage ?? current.usage
  };
}

function normalizeStreamEvent(rawEvent, requestedModel, finalMetadata = {}) {
  const delta = rawEvent?.delta?.text
    ?? rawEvent?.text
    ?? rawEvent?.content_block?.text;

  if (typeof delta === "string" && delta.length > 0) {
    return Object.freeze({
      type: STREAM_EVENT_TYPES.DELTA,
      provider: PROVIDER,
      model: rawEvent?.model ?? requestedModel,
      delta
    });
  }

  const completed = rawEvent?.type === "message_stop" || rawEvent?.done === true || rawEvent?.stop_reason;
  if (completed) {
    const message = rawEvent?.message ?? rawEvent;
    return Object.freeze({
      type: STREAM_EVENT_TYPES.FINAL,
      provider: PROVIDER,
      model: message?.model ?? requestedModel,
      finishReason: message?.stop_reason ?? message?.finish_reason ?? finalMetadata.finishReason ?? null,
      usage: normalizeUsage(message?.usage ?? finalMetadata.usage)
    });
  }

  return null;
}

function streamErrorEvent(model, error) {
  return Object.freeze({
    type: STREAM_EVENT_TYPES.ERROR,
    provider: PROVIDER,
    model: model ?? null,
    error
  });
}
