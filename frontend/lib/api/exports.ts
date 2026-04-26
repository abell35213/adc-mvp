/* ── Exports ──────────────────────────────────────────────────────── */

import { request } from "./core";
import type {
  ExportType,
  ExportStatus,
  ExportProgressStage,
  ExportSummary,
  ExportListItem,
  EventSummary,
  JsonObject,
  UtcTimestamp,
} from "./types";

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
  options_json?: JsonObject;
}

export interface CreateExportEnqueueResponse {
  export_id: string;
  incident_id: string;
  export_type: ExportType;
  status: ExportStatus;
  created_at_utc: UtcTimestamp;
}

export interface RetryExportRequest {
  export_type?: ExportType;
  options_json?: JsonObject;
}

export interface ExportStatusResponse {
  status: ExportStatus;
  progress_stage: ExportProgressStage;
  error_message?: string | null;
}

export interface ExportDownloadAuditResponse {
  export_id: string;
  downloads: EventSummary[];
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
