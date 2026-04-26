/** Thin wrapper around fetch for talking to the FastAPI backend. */

const API_BASE =
  typeof window === "undefined"
    ? process.env.API_INTERNAL_BASE_URL ??
      process.env.NEXT_PUBLIC_API_BASE_URL ??
      "http://localhost:8000"
    : process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type ApiErrorDetail = {
  message?: string;
  code?: string;
  retry_hint?: string;
  correlation_id?: string;
};

type ApiErrorPayload = {
  detail?: string | ApiErrorDetail;
};

export class ApiRequestError extends Error {
  status: number;
  code?: string;
  retryHint?: string;
  correlationId?: string;

  constructor(
    message: string,
    status: number,
    options: { code?: string; retryHint?: string; correlationId?: string } = {}
  ) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = options.code;
    this.retryHint = options.retryHint;
    this.correlationId = options.correlationId;
  }
}

/** Thrown when the network call itself fails (DNS, offline, CORS, etc.). */
export class ApiNetworkError extends Error {
  cause?: unknown;
  constructor(message: string, cause?: unknown) {
    super(message);
    this.name = "ApiNetworkError";
    this.cause = cause;
  }
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function parseApiErrorPayload(payload: unknown): {
  message?: string;
  code?: string;
  retryHint?: string;
  correlationId?: string;
} {
  if (!isPlainObject(payload)) return {};
  const detail = (payload as ApiErrorPayload).detail;
  if (typeof detail === "string") {
    return { message: detail };
  }
  if (!isPlainObject(detail)) return {};
  const d = detail as ApiErrorDetail;
  return {
    message: typeof d.message === "string" ? d.message : undefined,
    code: typeof d.code === "string" ? d.code : undefined,
    retryHint: typeof d.retry_hint === "string" ? d.retry_hint : undefined,
    correlationId: typeof d.correlation_id === "string" ? d.correlation_id : undefined,
  };
}

export function toUserErrorMessage(error: unknown, fallback = "Request failed"): string {
  if (!(error instanceof ApiRequestError)) {
    if (error instanceof Error && error.message) return error.message;
    return fallback;
  }

  const guidanceByCode: Record<string, string> = {
    EXPORT_DELAYED: "Export generation is taking longer than usual. Wait a minute, then try download again.",
    EXPORT_NOT_READY: "Export is still processing. Please check again shortly.",
    EXPORT_EXPIRED: "This export has expired. Generate a new export package to continue.",
    EXPORT_RETRY_ALLOWED: "Only failed exports can be retried. Wait for processing to complete first.",
    UPLOAD_RETRY_RECOMMENDED: "Upload processing is delayed. Retry the upload in a few moments.",
    THIRD_PARTY_DEGRADED: "A connected provider is degraded right now. Retry shortly.",
  };

  const guidance = error.code ? guidanceByCode[error.code] : undefined;
  const hint = error.retryHint ? ` ${error.retryHint}` : "";
  const correlation = error.correlationId ? ` (Ref: ${error.correlationId})` : "";

  return `${guidance ?? error.message ?? fallback}${hint}${correlation}`.trim();
}

/**
 * Merge `HeadersInit` (record, array, or `Headers`) into a single mutable
 * `Headers` instance, then ensure the JSON `Content-Type` default is set.
 */
function mergeHeaders(init: HeadersInit | undefined): Headers {
  const headers = new Headers(init);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return headers;
}

export async function request<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const headers = mergeHeaders(init?.headers);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers,
      credentials: init?.credentials ?? "include",
    });
  } catch (cause) {
    throw new ApiNetworkError(
      cause instanceof Error ? cause.message : "Network request failed",
      cause
    );
  }

  if (res.status === 401) {
    const isAuthMutation = path === "/auth/login" || path === "/auth/register";
    if (typeof window !== "undefined" && !isAuthMutation) {
      window.location.href = "/login";
    }
    throw new ApiRequestError("Unauthorized", 401);
  }

  if (!res.ok) {
    const body: unknown = await res.json().catch(() => null);
    const parsed = parseApiErrorPayload(body);
    throw new ApiRequestError(parsed.message ?? res.statusText, res.status, parsed);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  const contentType = res.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return res.json() as Promise<T>;
  }
  return undefined as T;
}

/* ── Query-string helper ────────────────────────────────────────── */

/**
 * Primitive value accepted by {@link buildQuery}.  Values of `undefined`,
 * `null`, or empty string are skipped so that callers can pass partially
 * filled `params` objects without having to guard each field.
 */
export type QueryValue = string | number | boolean | null | undefined;

/**
 * Build a URL query-string suffix (including the leading `?`) from a
 * record of primitives.  Returns `""` when no values are present.
 *
 * Skips entries whose value is `undefined`, `null`, or an empty string,
 * matching the behavior previously hand-rolled in each request helper.
 */
export function buildQuery<T extends { [K in keyof T]: QueryValue }>(
  params?: T | undefined
): string {
  if (!params) return "";
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params) as Array<[string, QueryValue]>) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}
