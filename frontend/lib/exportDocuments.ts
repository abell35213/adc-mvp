import type { ExportProgressStage, ExportStatus, ExportSummary, ExportType } from "@/lib/api";
import type { StatusTone } from "@/lib/design/tokens";

export const EXPORT_TYPE_LABELS: Record<ExportType, string> = {
  court_defense: "Legal Defense Packet",
  insurer_packet: "Insurance Notice",
  internal_review: "Crash Executive Brief",
  compliance_audit: "Agency Packet",
};

export const EXPORT_STAGE_LABELS: Record<ExportProgressStage, string> = {
  request_accepted: "Request accepted",
  gathering_incident_data: "Preparing case data",
  assembling_documents: "Rendering packet",
  packaging_evidence: "Packaging evidence",
  uploading_export: "Uploading document",
  ready_for_download: "Ready for download",
};

export const EXPORT_STATUS_COPY: Record<ExportStatus, { label: string; tone: StatusTone; description: string }> = {
  requested: { label: "Requested", tone: "info", description: "Document generation has been requested." },
  queued: { label: "Queued", tone: "warning", description: "Document generation is queued and will start shortly." },
  processing: { label: "Generating", tone: "info", description: "ADC is assembling the case document." },
  ready: { label: "Ready", tone: "success", description: "Document is ready to download." },
  failed: { label: "Needs attention", tone: "critical", description: "Document could not be generated." },
  expired: { label: "Expired", tone: "critical", description: "The download is no longer available." },
};

const TERMINAL: ExportStatus[] = ["ready", "failed", "expired"];
const PRIORITY: Record<ExportStatus, number> = { failed: 0, expired: 1, ready: 2, processing: 3, queued: 4, requested: 5 };

export interface ExportDocumentViewModel {
  id: string;
  incidentId: string | null;
  title: string;
  typeLabel: string;
  caseReference: string;
  incidentContext: string;
  status: ExportStatus;
  statusLabel: string;
  statusTone: StatusTone;
  statusDescription: string;
  stageLabel: string;
  requestedBy: string;
  generatedLabel: string;
  generatedTitle: string;
  fileMeta: string;
  versionLabel: string | null;
  safeFailureReason: string | null;
  missingRequirements: string[];
  canDownload: boolean;
  canRetry: boolean;
  canRegenerate: boolean;
  isTerminal: boolean;
  technicalIdLabel: string;
  searchText: string;
}

export function shortId(id?: string | null): string {
  return id ? id.slice(0, 8).toUpperCase() : "UNKNOWN";
}

export function formatBytes(size?: number | null): string {
  if (size == null || size < 0) return "—";
  if (size < 1024) return `${size} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = size / 1024;
  let idx = 0;
  while (value >= 1024 && idx < units.length - 1) { value /= 1024; idx += 1; }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[idx]}`;
}

export function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

export function relevantTimestamp(item: ExportSummary): string | null | undefined {
  if (item.status === "ready") return item.completed_at_utc ?? item.updated_at_utc ?? item.created_at_utc;
  if (item.status === "failed" || item.status === "expired") return item.updated_at_utc ?? item.completed_at_utc ?? item.created_at_utc;
  return item.processing_started_at_utc ?? item.requested_at_utc ?? item.created_at_utc;
}

export function safeFailureReason(item: ExportSummary): string | null {
  const raw = item.failure_reason || item.error_message || (typeof item.options_json?.failure_reason === "string" ? item.options_json.failure_reason : null);
  const code = typeof item.options_json?.failure_code === "string" ? item.options_json.failure_code : null;
  if (code === "missing_police_report") return "The police report is still missing.";
  if (code === "missing_required_evidence") return "Required case evidence is still missing.";
  if (!raw) return item.status === "failed" ? "Document rendering failed. Retry generation or contact support if the problem continues." : null;
  if (/traceback|exception|sql|stack|s3|aws|credential|password|secret/i.test(raw)) return "Document rendering failed. Retry generation or contact support if the problem continues.";
  return raw;
}

export function missingRequirements(item: ExportSummary): string[] {
  const values = item.options_json?.missing_items;
  if (!Array.isArray(values)) return [];
  return values.map((entry) => {
    if (typeof entry === "string") return entry;
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) return "Missing requirement";
    const record = entry as Record<string, unknown>;
    if (typeof record.message === "string") return record.message;
    if (typeof record.code === "string") return record.code.replaceAll("_", " ");
    return "Missing requirement";
  }).slice(0, 4);
}

export function buildExportDocumentViewModel(item: ExportSummary): ExportDocumentViewModel {
  const typeLabel = EXPORT_TYPE_LABELS[item.export_type] ?? item.export_type.replaceAll("_", " ");
  const title = typeof item.options_json?.document_title === "string" ? item.options_json.document_title : typeLabel;
  const incidentId = item.incident_id ?? null;
  const caseReference = typeof item.options_json?.case_reference === "string" ? item.options_json.case_reference : `Case ${shortId(incidentId)}`;
  const incidentContext = typeof item.options_json?.incident_display_context === "string" ? item.options_json.incident_display_context : "Incident workspace";
  const status = EXPORT_STATUS_COPY[item.status];
  const requestedBy = typeof item.options_json?.requested_by_display_name === "string" ? item.options_json.requested_by_display_name : item.requested_by_user_id ? "Authorized user" : "—";
  const generated = relevantTimestamp(item);
  const fileName = typeof item.options_json?.file_name === "string" ? item.options_json.file_name : item.status === "ready" ? `${title}.zip` : null;
  const size = typeof item.options_json?.file_size_bytes === "number" ? item.options_json.file_size_bytes : item.byte_size;
  const version = typeof item.options_json?.version === "string" || typeof item.options_json?.version === "number" ? `v${item.options_json.version}` : item.retry_parent_export_id ? "Retry attempt" : null;
  return {
    id: item.export_id,
    incidentId,
    title,
    typeLabel,
    caseReference,
    incidentContext,
    status: item.status,
    statusLabel: status.label,
    statusTone: status.tone,
    statusDescription: status.description,
    stageLabel: EXPORT_STAGE_LABELS[item.progress_stage] ?? "Preparing document",
    requestedBy,
    generatedLabel: formatDateTime(generated),
    generatedTitle: generated ?? "",
    fileMeta: [fileName, size ? formatBytes(size) : null].filter(Boolean).join(" · ") || "File pending",
    versionLabel: version,
    safeFailureReason: safeFailureReason(item),
    missingRequirements: missingRequirements(item),
    canDownload: item.status === "ready",
    canRetry: item.status === "failed",
    canRegenerate: item.status === "expired" || item.status === "ready",
    isTerminal: TERMINAL.includes(item.status),
    technicalIdLabel: `Export ${shortId(item.export_id)}`,
    searchText: [title, typeLabel, caseReference, incidentId, fileName, item.export_id].filter(Boolean).join(" ").toLowerCase(),
  };
}

export function sortExportDocuments(items: ExportSummary[]): ExportSummary[] {
  return [...items].sort((a, b) => (PRIORITY[a.status] - PRIORITY[b.status]) || (new Date(relevantTimestamp(b) ?? 0).getTime() - new Date(relevantTimestamp(a) ?? 0).getTime()) || a.export_id.localeCompare(b.export_id));
}
