import { normalizeUsage } from "./usage.js";

const ALLOWED_FIELDS = new Set([
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
  "dependencyStatus"
]);

const FORBIDDEN_FIELD_PATTERNS = [
  /prompt/i,
  /message/i,
  /content/i,
  /response/i,
  /output/i,
  /completion/i,
  /selected.*text/i,
  /document.*text/i,
  /api.*key/i,
  /credential/i,
  /secret/i,
  /authorization/i,
  /cookie/i,
  /bearer/i,
  /oauth/i,
  /access.*token/i,
  /refresh.*token/i
];

export function sanitizeLogFields(fields) {
  if (!fields || typeof fields !== "object" || Array.isArray(fields)) {
    throw new TypeError("Log fields must be an object.");
  }

  assertNoForbiddenFields(fields);

  const safe = {};
  for (const [key, value] of Object.entries(fields)) {
    if (!ALLOWED_FIELDS.has(key) || value === undefined) {
      continue;
    }
    safe[key] = key === "tokenUsage" ? normalizeUsage(value) : value;
  }

  return Object.freeze(safe);
}

export function createSafeLogger(sink = console) {
  return Object.freeze({
    info(fields) {
      write(sink, "info", fields);
    },
    warn(fields) {
      write(sink, "warn", fields);
    },
    error(fields) {
      write(sink, "error", fields);
    }
  });
}

function write(sink, level, fields) {
  const safeFields = sanitizeLogFields(fields);
  const writer = typeof sink[level] === "function" ? sink[level].bind(sink) : sink.log.bind(sink);
  writer(safeFields);
}

function assertNoForbiddenFields(value, path = []) {
  if (!value || typeof value !== "object") {
    return;
  }

  for (const [key, nested] of Object.entries(value)) {
    const nextPath = [...path, key];
    if (FORBIDDEN_FIELD_PATTERNS.some((pattern) => pattern.test(key))) {
      throw new TypeError(`Forbidden log field: ${nextPath.join(".")}`);
    }
    assertNoForbiddenFields(nested, nextPath);
  }
}
