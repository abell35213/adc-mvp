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
  profile_id: string;
  requested_by_user_id?: string | null;
  retry_parent_export_id?: string | null;
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

export interface RetryExportRequest {
  export_type?: ExportType;
  options_json?: Record<string, unknown>;
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

export function retryExport(exportId: string, data: RetryExportRequest = {}) {
  return request<CreateExportEnqueueResponse>(`/exports/${exportId}/retry`, {
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

export interface OpsIncidentItem {
  incident_id: string;
  status: string;
  created_at_utc?: string | null;
  adc_vehicle_id?: string | null;
  adc_driver_id?: string | null;
  reason: string;
}

export interface OpsFailedNotificationItem {
  celery_task_id: string;
  status: string;
  retry_count: number;
  max_retries?: number | null;
  last_error?: string | null;
  updated_at_utc?: string | null;
}

export interface OpsFailedExportItem {
  export_id: string;
  incident_id: string;
  export_type: ExportType;
  status: ExportStatus;
  error_message?: string | null;
  updated_at_utc?: string | null;
}

export interface IntegrationHealthItem {
  integration_key: string;
  status: "healthy" | "degraded";
  failure_count: number;
  last_failure_at_utc?: string | null;
  details?: string | null;
}

export interface OpsAnomalyItem {
  audit_event_id: string;
  occurred_at_utc: string;
  action: string;
  event_type: string;
  outcome?: string | null;
  actor_id: string;
  metadata: Record<string, unknown>;
}

export interface OpsDashboardResponse {
  stuck_incidents: OpsIncidentItem[];
  missing_evidence_incidents: OpsIncidentItem[];
  failed_notifications: OpsFailedNotificationItem[];
  failed_exports: OpsFailedExportItem[];
  integration_health: IntegrationHealthItem[];
  recent_anomalies: OpsAnomalyItem[];
}

export interface AuditSearchResponseItem {
  audit_event_id: string;
  org_id: string;
  incident_id?: string | null;
  export_id?: string | null;
  actor_type: string;
  actor_id: string;
  action: string;
  event_type: string;
  outcome?: string | null;
  occurred_at_utc: string;
  metadata: Record<string, unknown>;
}

export function getOpsDashboard(params?: {
  stale_after_minutes?: number;
  lookback_hours?: number;
}) {
  const query = new URLSearchParams();
  if (params?.stale_after_minutes) {
    query.set("stale_after_minutes", String(params.stale_after_minutes));
  }
  if (params?.lookback_hours) {
    query.set("lookback_hours", String(params.lookback_hours));
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<OpsDashboardResponse>(`/admin/ops/dashboard${suffix}`);
}

export function searchOpsAudit(params?: {
  q?: string;
  action?: string;
  event_type?: string;
  outcome?: string;
  actor_id?: string;
  lookback_hours?: number;
  limit?: number;
}) {
  const query = new URLSearchParams();
  if (params?.q) query.set("q", params.q);
  if (params?.action) query.set("action", params.action);
  if (params?.event_type) query.set("event_type", params.event_type);
  if (params?.outcome) query.set("outcome", params.outcome);
  if (params?.actor_id) query.set("actor_id", params.actor_id);
  if (params?.lookback_hours) query.set("lookback_hours", String(params.lookback_hours));
  if (params?.limit) query.set("limit", String(params.limit));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<AuditSearchResponseItem[]>(`/admin/ops/audit-search${suffix}`);
}
