/**
 * Pure JS helpers shared between `core.ts` (typed wrappers) and the
 * `node:test` suite.  Keeping them in a `.mjs` module avoids needing a
 * TypeScript runtime in tests while preserving a single source of truth.
 */

/**
 * Build a URL query-string suffix (including leading `?`) from a record
 * of primitives.  Returns `""` when no values remain after skipping
 * `undefined`, `null`, and empty-string values.
 */
export function buildQuery(params) {
  if (!params) return "";
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

function isPlainObject(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Defensively normalize an arbitrary error payload returned by the
 * FastAPI backend into a flat record of optional string fields.
 *
 * Accepts:
 *   • `{ detail: "..." }`               → `{ message }`
 *   • `{ detail: { message, code, retry_hint, correlation_id } }`
 *   • `null` / non-object / arrays      → `{}`
 *
 * Any non-string field on the detail object is dropped rather than
 * surfaced as `undefined.something` to downstream consumers.
 */
export function parseApiErrorPayload(payload) {
  if (!isPlainObject(payload)) return {};
  const detail = payload.detail;
  if (typeof detail === "string") return { message: detail };
  if (!isPlainObject(detail)) return {};
  return {
    message: typeof detail.message === "string" ? detail.message : undefined,
    code: typeof detail.code === "string" ? detail.code : undefined,
    retryHint:
      typeof detail.retry_hint === "string" ? detail.retry_hint : undefined,
    correlationId:
      typeof detail.correlation_id === "string"
        ? detail.correlation_id
        : undefined,
  };
}
