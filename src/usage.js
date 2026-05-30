export function normalizeUsage(rawUsage = {}) {
  const inputTokens = numberOrZero(rawUsage.inputTokens ?? rawUsage.input_tokens);
  const outputTokens = numberOrZero(rawUsage.outputTokens ?? rawUsage.output_tokens);
  const totalTokens = numberOrZero(rawUsage.totalTokens ?? rawUsage.total_tokens ?? inputTokens + outputTokens);

  return Object.freeze({
    inputTokens,
    outputTokens,
    totalTokens
  });
}

function numberOrZero(value) {
  return Number.isFinite(value) && value >= 0 ? value : 0;
}
