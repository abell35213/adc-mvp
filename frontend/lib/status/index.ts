import type { CaseStatus, ExportStatus, IncidentStatus } from "@/lib/api";
import { statusBadgeClass, type StatusTone } from "@/lib/design/tokens";

export interface StatusMeta {
  label: string;
  tone: StatusTone;
}

export interface StatusOption<T extends string> {
  value: T;
  label: string;
}

const titleize = (value: string): string => value.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());

const UNKNOWN_STATUS_META: StatusMeta = {
  label: "Unknown",
  tone: "neutral",
};

export const CASE_STATUS_META: Record<CaseStatus, StatusMeta> = {
  new: { label: "New", tone: "info" },
  in_review: { label: "In review", tone: "warning" },
  awaiting_evidence: { label: "Awaiting evidence", tone: "warning" },
  awaiting_follow_up: { label: "Awaiting follow up", tone: "warning" },
  ready_for_export: { label: "Ready for export", tone: "success" },
  exported: { label: "Exported", tone: "success" },
  escalated: { label: "Escalated", tone: "critical" },
  closed: { label: "Closed", tone: "success" },
};

export const INCIDENT_STATUS_META: Record<IncidentStatus, StatusMeta> = {
  open: { label: "Open", tone: "info" },
  evidence_capturing: { label: "Capturing evidence", tone: "warning" },
  closed: { label: "Closed", tone: "success" },
};

const READINESS_META = {
  not_started: { label: "Not started", tone: "neutral" },
  in_progress: { label: "In progress", tone: "warning" },
  blocked: { label: "Blocked", tone: "critical" },
  ready: { label: "Ready", tone: "success" },
  not_ready: { label: "Not ready", tone: "critical" },
  conditionally_ready: { label: "Conditionally ready", tone: "warning" },
  ready_for_export: { label: "Ready for export", tone: "success" },
  exported: { label: "Exported", tone: "success" },
  closed: { label: "Closed", tone: "success" },
} as const satisfies Record<string, StatusMeta>;

export type ReadinessState = keyof typeof READINESS_META;

const EVIDENCE_META = {
  missing: { label: "Missing", tone: "critical" },
  partial: { label: "Partial", tone: "warning" },
  complete: { label: "Complete", tone: "success" },
  pending: { label: "Pending", tone: "warning" },
  captured: { label: "Captured", tone: "success" },
  unavailable: { label: "Unavailable", tone: "critical" },
} as const satisfies Record<string, StatusMeta>;

export type EvidenceState = keyof typeof EVIDENCE_META;

export const EXPORT_STATE_META: Record<ExportStatus, StatusMeta> = {
  requested: { label: "Requested", tone: "warning" },
  queued: { label: "Queued", tone: "warning" },
  processing: { label: "Processing", tone: "warning" },
  ready: { label: "Ready", tone: "success" },
  failed: { label: "Failed", tone: "critical" },
  expired: { label: "Expired", tone: "critical" },
};

const EXPORT_STATUS_VALUES = ["requested", "queued", "processing", "ready", "failed", "expired"] as const;
const READINESS_STATUS_VALUES = ["not_ready", "conditionally_ready", "ready_for_export", "exported", "closed"] as const;

export const EXPORT_STATUS_OPTIONS: StatusOption<ExportStatus>[] = EXPORT_STATUS_VALUES.map((value) => ({
  value,
  label: EXPORT_STATE_META[value].label,
}));

export const READINESS_STATUS_OPTIONS: StatusOption<ReadinessState>[] = READINESS_STATUS_VALUES.map((value) => ({
  value,
  label: READINESS_META[value].label,
}));

export function getCaseStatusMeta(status: string): StatusMeta {
  if (Object.prototype.hasOwnProperty.call(CASE_STATUS_META, status)) return CASE_STATUS_META[status as CaseStatus];
  if (Object.prototype.hasOwnProperty.call(INCIDENT_STATUS_META, status)) return INCIDENT_STATUS_META[status as IncidentStatus];
  if (!status) return UNKNOWN_STATUS_META;
  return { label: titleize(status), tone: "neutral" };
}

export function getReadinessMeta(state: string): StatusMeta {
  if (Object.prototype.hasOwnProperty.call(READINESS_META, state)) return READINESS_META[state as ReadinessState];
  if (!state) return UNKNOWN_STATUS_META;
  return { label: titleize(state), tone: "neutral" };
}

export function getEvidenceMeta(state: string): StatusMeta {
  if (Object.prototype.hasOwnProperty.call(EVIDENCE_META, state)) return EVIDENCE_META[state as EvidenceState];
  if (!state) return UNKNOWN_STATUS_META;
  return { label: titleize(state), tone: "neutral" };
}

export function getExportStateMeta(state: ExportStatus): StatusMeta {
  return EXPORT_STATE_META[state];
}

export function getStatusBadgeClass(tone: StatusTone): string {
  return statusBadgeClass(tone);
}
