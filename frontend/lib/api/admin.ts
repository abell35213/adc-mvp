/* ── Admin ─────────────────────────────────────────────────────── */

import { request } from "./core";
import type { ImportJobStatus, ExportType, ExportStatus } from "./types";

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

export interface AdminVehicle {
  adc_vehicle_id: string;
  display_label: string;
}

export interface VehicleImportJobSummary {
  missing_qr_count: number;
  missing_provider_mapping_count: number;
  duplicate_like_count: number;
  inactive_count: number;
}

export interface VehicleImportJobOutcome {
  imported: string[];
  updated: string[];
  skipped: string[];
  errored: string[];
}

export interface VehicleImportJobResponse {
  job_id: string;
  provider: string;
  status: ImportJobStatus;
  started_at_utc?: string | null;
  completed_at_utc?: string | null;
  records_total: number;
  records_processed: number;
  records_imported: number;
  records_updated: number;
  records_skipped: number;
  records_errored: number;
  warnings: string[];
  outcomes: VehicleImportJobOutcome;
  summary: VehicleImportJobSummary;
  error_message?: string | null;
}

export interface DriverImportJobSummary {
  invalid_phone_count: number;
  duplicate_warning_count: number;
  missing_assignment_count: number;
  missing_external_mapping_count: number;
  needs_review_count: number;
  inactive_count: number;
}

export interface DriverImportJobOutcome {
  imported: string[];
  updated: string[];
  skipped: string[];
  errored: string[];
  invalid_phone: string[];
  duplicate_warning: string[];
  missing_assignment_or_mapping: string[];
  needs_review: string[];
}

export interface DriverImportJobResponse {
  job_id: string;
  provider: string;
  status: ImportJobStatus;
  started_at_utc?: string | null;
  completed_at_utc?: string | null;
  records_total: number;
  records_processed: number;
  records_imported: number;
  records_updated: number;
  records_skipped: number;
  records_errored: number;
  warnings: string[];
  outcomes: DriverImportJobOutcome;
  summary: DriverImportJobSummary;
  error_message?: string | null;
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

export function createVehicleImportJob(data: {
  provider: string;
  csv_content: string;
  header_mapping: Record<string, string>;
  inactive_unit_numbers: string[];
}) {
  return request<{ job_id: string; status: ImportJobStatus }>("/org/vehicles/import", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function getVehicleImportJob(jobId: string) {
  return request<VehicleImportJobResponse>(`/org/vehicles/import-jobs/${jobId}`);
}

export function createDriverImportJob(data: {
  provider: string;
  csv_content: string;
  header_mapping: Record<string, string>;
  inactive_mobile_phones: string[];
}) {
  return request<{ job_id: string; status: ImportJobStatus }>("/org/drivers/import", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function getDriverImportJob(jobId: string) {
  return request<DriverImportJobResponse>(`/org/drivers/import-jobs/${jobId}`);
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
