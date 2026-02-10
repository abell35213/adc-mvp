/** Thin wrapper around fetch for talking to the FastAPI backend. */

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: init?.credentials ?? "include",
  });

  if (res.status === 401) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? res.statusText);
  }

  return res.json() as Promise<T>;
}

/* ── Auth ──────────────────────────────────────────────────────── */

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role: string;
}

export async function login(email: string, password: string) {
  const data = await request<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  localStorage.setItem("token", data.access_token);
  return data;
}

export interface RegisterResponse {
  user_id: string;
  email: string;
  role: string;
  org_id: string;
  access_token: string;
}

export async function register(
  email: string,
  password: string,
  role = "safety_manager",
  orgName = "Default"
) {
  const data = await request<RegisterResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, role, org_name: orgName }),
  });
  localStorage.setItem("token", data.access_token);
  return data;
}

export function logout() {
  const token = localStorage.getItem("token");
  if (token) {
    // Fire-and-forget; clear local state regardless
    fetch(`${API_BASE}/auth/logout`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
    }).catch(() => {});
  }
  localStorage.removeItem("token");
  window.location.href = "/login";
}

export interface MeResponse {
  user_id: string;
  email: string;
  role: string;
  org_ids: string[];
}

export function getMe() {
  return request<MeResponse>("/auth/me");
}

/* ── Incidents ─────────────────────────────────────────────────── */

export interface Incident {
  incident_id: string;
  status: string;
  severity: string | null;
  adc_vehicle_id: string | null;
  samsara_vehicle_id: string | null;
  adc_driver_id: string | null;
  created_at_utc?: string;
  evidence_captured?: number;
  evidence_total?: number;
}

export interface ArtifactSummary {
  artifact_id: string;
  artifact_type: string;
  status: string;
  captured_at_utc?: string | null;
  unavailable_reason?: string | null;
}

export interface ExportSummary {
  export_id: string;
  status: string;
  created_at_utc?: string | null;
}

export interface EventSummary {
  event_type: string;
  occurred_at_utc: string;
  actor_type: string;
  payload?: Record<string, unknown> | null;
}

export interface IncidentDetail extends Incident {
  evidence_inventory: ArtifactSummary[];
  export_status: ExportSummary[];
  timeline: EventSummary[];
}

export function listIncidents() {
  return request<Incident[]>("/incidents/");
}

export function createIncident(data: {
  severity: string;
  adc_vehicle_id: string;
  samsara_vehicle_id: string;
  adc_driver_id: string;
  window_start?: string;
  window_end?: string;
}) {
  return request<{ incident_id: string; status: string }>("/incidents/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function getIncident(id: string) {
  return request<IncidentDetail>(`/incidents/${id}`);
}

export function requestExport(incidentId: string) {
  return request<{ export_id: string; status: string }>(
    `/incidents/${incidentId}/exports`,
    { method: "POST" }
  );
}

export function downloadExport(exportId: string) {
  return request<{ export_id: string; url: string; status: string }>(
    `/exports/${exportId}/download`
  );
}
