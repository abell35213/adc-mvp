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

function parseApiErrorPayload(payload: ApiErrorPayload | null | undefined) {
  const detail = payload?.detail;
  if (typeof detail === "string") {
    return { message: detail };
  }
  return {
    message: detail?.message,
    code: detail?.code,
    retryHint: detail?.retry_hint,
    correlationId: detail?.correlation_id,
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

export async function request<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string>),
  };

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: init?.credentials ?? "include",
  });

  if (res.status === 401) {
    const isAuthMutation = path === "/auth/login" || path === "/auth/register";
    if (typeof window !== "undefined" && !isAuthMutation) {
      window.location.href = "/login";
    }
    throw new ApiRequestError("Unauthorized", 401);
  }

  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as ApiErrorPayload;
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
