/** Thin wrapper around fetch for talking to the FastAPI backend. */

const API_BASE =
  typeof window === "undefined"
    ? process.env.API_INTERNAL_BASE_URL ??
      process.env.NEXT_PUBLIC_API_BASE_URL ??
      "http://localhost:8000"
    : process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(
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
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? res.statusText);
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

/* ── Auth ──────────────────────────────────────────────────────── */

export interface LoginResponse {
  user: MeResponse;
}

export async function login(email: string, password: string) {
  await request<void>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  const user = await getMe();
  return { user } satisfies LoginResponse;
}

export interface RegisterResponse {
  user: MeResponse;
  user_id: string;
  email: string;
  role: string;
  org_id: string;
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
  const user = await getMe();
  return { ...data, user };
}

export function logout() {
  return request<void>("/auth/logout", {
    method: "POST",
  }).finally(() => {
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  });
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


export type ExportType =
  | "court_defense"
  | "insurer_packet"
  | "internal_review"
  | "compliance_audit";

export type ExportStatus =
  | "requested"
  | "queued"
  | "processing"
  | "ready"
  | "failed"
  | "expired";

export type ExportProgressStage =
  | "request_accepted"
  | "gathering_incident_data"
  | "assembling_documents"
  | "packaging_evidence"
  | "uploading_export"
  | "ready_for_download";

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
  driver_response?: DriverResponseSummary | null;
  driver_protocol_summary?: DriverProtocolSummary | null;
}

export interface DriverResponseSummary {
  notification_sent_at_utc?: string | null;
  acknowledged_at_utc?: string | null;
  uploads_complete?: boolean;
  uploads_completed_at_utc?: string | null;
  awaiting_driver_action?: boolean;
}

export interface DriverProtocolSummary {
  instruction_source?: string;
  require_ack?: boolean;
  sms_enabled?: boolean;
  voice_enabled?: boolean;
  safety_manager_phone?: string | null;
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
  incident_id?: string | null;
  export_type: ExportType;
  requested_by_user_id?: string | null;
  options_json: Record<string, unknown>;
  status: ExportStatus;
  progress_stage: ExportProgressStage;
  error_message?: string | null;
  package_sha256?: string | null;
  byte_size?: number | null;
  artifact_count: number;
  timeline_event_count: number;
  requested_at_utc?: string | null;
  processing_started_at_utc?: string | null;
  completed_at_utc?: string | null;
  expires_at_utc?: string | null;
  created_at_utc?: string | null;
  updated_at_utc?: string | null;
  generated_by?: string | null;
  generation_duration_seconds?: number | null;
  failure_count?: number | null;
  failure_reason?: string | null;
  retry_guidance?: string | null;
  readiness?: {
    required_artifacts_present?: boolean | null;
    custody_complete?: boolean | null;
    integrity_checks_passed?: boolean | null;
  } | null;
}

/**
 * A summary of an export along with its originating incident.  When
 * listing all exports across an organization, the backend returns the
 * associated incident_id so that the UI can link back to the incident
 * detail page.  This structure extends the base ExportSummary.
 */
export interface ExportListItem extends ExportSummary {
  /**
   * Identifier of the incident this export belongs to.  Useful for
   * navigating back to the source incident after downloading a package.
   */
  incident_id: string;
}

export interface EventSummary {
  event_type: string;
  occurred_at_utc: string;
  actor_type: string;
  payload?: Record<string, unknown> | null;
}

export interface ExportDownloadAuditResponse {
  export_id: string;
  downloads: EventSummary[];
}

export type ExportContentsClassification =
  | "included"
  | "unavailable"
  | "excluded_by_option"
  | "failed_to_retrieve";

export interface ExportContentsItem {
  kind: string;
  item?: string | null;
  path?: string | null;
  classification: ExportContentsClassification;
  included: boolean;
  reason?: string | null;
  byte_size?: number | null;
}

export interface ExportContentsResponse {
  export_id: string;
  status: ExportStatus;
  progress_stage: ExportProgressStage;
  file_manifest: ExportContentsItem[];
  missing_items: Array<Record<string, string>>;
  warnings: Array<Record<string, string>>;
}

export interface CreateExportRequest {
  incident_id: string;
  export_type: ExportType;
  options_json?: Record<string, unknown>;
}

export interface CreateExportEnqueueResponse {
  export_id: string;
  incident_id: string;
  export_type: ExportType;
  status: ExportStatus;
  created_at_utc: string;
}

export interface ExportStatusResponse {
  status: ExportStatus;
  progress_stage: ExportProgressStage;
  error_message?: string | null;
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
  return request<{ export_id: string; status: ExportStatus; progress_stage: ExportProgressStage }>(
    `/incidents/${incidentId}/exports`,
    { method: "POST" }
  );
}

export function createExport(data: CreateExportRequest) {
  return request<CreateExportEnqueueResponse>("/exports/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function getExport(exportId: string) {
  return request<ExportSummary>(`/exports/${exportId}`);
}

export function getExportStatus(exportId: string) {
  return request<ExportStatusResponse>(`/exports/${exportId}/status`);
}

export function downloadExport(exportId: string) {
  return request<{ export_id: string; url: string; status: ExportStatus; progress_stage: ExportProgressStage }>(
    `/exports/${exportId}/download`
  );
}

export function getExportDownloadHistory(exportId: string) {
  return request<ExportDownloadAuditResponse>(`/exports/${exportId}/downloads`);
}

export function getExportContents(exportId: string) {
  return request<ExportContentsResponse>(`/exports/${exportId}/contents`);
}

/* ── Exports listing ──────────────────────────────────────────────── */

/**
 * Retrieve all exports visible to the current user.  The backend
 * responds with a list of export summaries including the incident
 * identifier for each export.  This allows the frontend to display
 * exports in a standalone listing page and provide links back to the
 * incident detail view.
 */
export function listExports() {
  return request<ExportListItem[]>("/exports/");
}

/* ── Admin driver protocol ─────────────────────────────────────── */

export interface DriverProtocolSettings {
  instruction_source: string;
  require_ack: boolean;
  sms_enabled: boolean;
  voice_enabled: boolean;
  safety_manager_phone: string | null;
}

export function getDriverProtocolSettings() {
  return request<DriverProtocolSettings>("/admin/driver-protocol/settings");
}

export function updateDriverProtocolSettings(data: DriverProtocolSettings) {
  return request<DriverProtocolSettings>("/admin/driver-protocol/settings", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export interface DriverInstructionStep {
  step_id?: string;
  order: number;
  title: string;
  body: string;
  enabled: boolean;
}

export interface DriverInstructionSet {
  instruction_set_id: string;
  scope: string;
  steps: DriverInstructionStep[];
}

export function getDriverProtocolInstructions(scope?: string) {
  const query = scope ? `?scope=${encodeURIComponent(scope)}` : "";
  return request<DriverInstructionSet>(
    `/admin/driver-protocol/instructions${query}`
  );
}

export function updateDriverProtocolInstructions(data: {
  scope: string;
  steps: DriverInstructionStep[];
}) {
  return request<DriverInstructionSet>("/admin/driver-protocol/instructions", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export function resetDriverProtocolInstructions(scope?: string) {
  const query = scope ? `?scope=${encodeURIComponent(scope)}` : "";
  return request<DriverInstructionSet>(
    `/admin/driver-protocol/instructions/reset${query}`,
    { method: "POST" }
  );
}

/* ── Admin vehicles ─────────────────────────────────────────────── */

export interface AdminVehicle {
  adc_vehicle_id: string;
  display_label: string;
}

export function listAdminVehicles() {
  return request<AdminVehicle[]>("/admin/vehicles");
}

export function rotateVehicleQr(vehicleId: string) {
  return request<{ qr_token: string }>(
    `/admin/vehicles/${vehicleId}/qr/rotate`,
    { method: "POST" }
  );
}

export function getVehicleQrPayload(vehicleId: string) {
  return request<{ deep_link: string }>(`/admin/vehicles/${vehicleId}/qr`);
}
