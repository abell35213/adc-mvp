import type { ArtifactSummary, CaseWorkspaceResponse, ExportSummary, IncidentDetail, IncidentNoteItem, IncidentTaskItem } from "@/lib/api";
import { EVIDENCE_TYPES } from "@/lib/evidenceTypes";
import type { StatusTone } from "@/lib/design/tokens";

export type WorkspaceTab = "overview" | "evidence" | "timeline" | "documents" | "activity";

type Blocker = { code?: string; message?: string; severity?: string; category?: string; actionHint?: string; blocksReadiness?: boolean; blocks_readiness?: boolean };

export interface IncidentWorkspaceViewModel {
  caseReference: string;
  title: string;
  statusLabel: string;
  statusTone: StatusTone;
  readinessLabel: string;
  readinessTone: StatusTone;
  readinessPercent: number;
  createdLabel: string;
  createdAbsolute: string;
  updatedLabel: string;
  location: string;
  ownerLabel: string;
  driverLabel: string;
  vehicleLabel: string;
  narrative: string;
  blockers: { critical: Blocker[]; important: Blocker[]; recommended: Blocker[] };
  missingItems: string[];
  evidenceGroups: EvidenceGroup[];
  documentGroups: DocumentGroup[];
  timelineItems: TimelineItem[];
  activityItems: ActivityItem[];
  nextAction: NextAction;
}

export interface EvidenceGroup { id: string; title: string; items: EvidenceItem[] }
export interface EvidenceItem { id: string; label: string; status: string; statusTone: StatusTone; capturedAt: string; source: string; detail: string }
export interface DocumentGroup { id: string; title: string; items: DocumentItem[] }
export interface DocumentItem { id: string; title: string; status: string; statusTone: StatusTone; createdAt: string; primaryAction: "download" | "retry" | "view" | "none"; exportId: string }
export interface TimelineItem { id: string; title: string; timestamp: string; absolute: string; actor: string; description: string; technical: string }
export interface ActivityItem { id: string; title: string; timestamp: string; body: string; actor: string; kind: "note" | "task"; taskStatus?: IncidentTaskItem["status"] }
export interface NextAction { label: string; reason: string; kind: "missing_evidence" | "blockers" | "download" | "generate" | "update" }

export function formatDateTime(iso?: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });
}

export function relativeTime(iso?: string | null, now = new Date()): string {
  if (!iso) return "Not recorded";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Not recorded";
  const minutes = Math.max(0, Math.round((now.getTime() - date.getTime()) / 60000));
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

export function humanize(value?: string | null): string {
  if (!value) return "—";
  return value.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function shortId(id?: string | null): string { return id ? `${id.slice(0, 8)}…` : "—"; }
function caseReference(id: string): string { return `Case ${id.slice(0, 8).toUpperCase()}`; }
function statusTone(status?: string): StatusTone { if (status === "closed" || status === "exported" || status === "ready_for_export") return "success"; if (status === "escalated") return "critical"; if (status?.includes("awaiting")) return "warning"; return "info"; }
function readinessTone(readiness?: string): StatusTone { if (readiness === "ready" || readiness === "ready_for_export") return "success"; if (readiness === "conditionally_ready") return "warning"; return "critical"; }
function evidenceTone(status?: string): StatusTone { if (status === "captured" || status === "available") return "success"; if (status === "unavailable" || status === "failed" || status === "rejected" || status === "expired") return "critical"; if (status === "pending" || status === "requested" || status === "queued" || status === "processing") return "warning"; return "neutral"; }
function exportTone(status?: string): StatusTone { if (status === "ready") return "success"; if (status === "failed" || status === "expired") return "critical"; if (status === "queued" || status === "processing" || status === "requested") return "warning"; return "neutral"; }

export function groupBlockers(blockers: Blocker[] = []) {
  return blockers.reduce(
    (acc, blocker) => {
      const severity = String(blocker.severity ?? "").toLowerCase();
      if (severity === "critical" || severity === "error" || blocker.blocksReadiness || blocker.blocks_readiness) acc.critical.push(blocker);
      else if (severity === "warning") acc.important.push(blocker);
      else acc.recommended.push(blocker);
      return acc;
    },
    { critical: [] as Blocker[], important: [] as Blocker[], recommended: [] as Blocker[] },
  );
}

export function buildEvidenceGroups(artifacts: ArtifactSummary[]): EvidenceGroup[] {
  const map = new Map(artifacts.map((artifact) => [artifact.artifact_type, artifact]));
  return [{ id: "required", title: "Required evidence", items: EVIDENCE_TYPES.map(({ type, label }) => {
    const artifact = map.get(type);
    const status = artifact?.status ?? "pending";
    return { id: artifact?.artifact_id ?? type, label, status, statusTone: evidenceTone(status), capturedAt: formatDateTime(artifact?.captured_at_utc), source: type.includes("dashcam") ? "Dashcam" : type.includes("eld") || type.includes("gps") ? "Telematics" : "ADC", detail: artifact?.unavailable_reason ?? "No exceptions recorded" };
  }) }];
}

export function buildDocumentGroups(exports: ExportSummary[]): DocumentGroup[] {
  const items = exports.map((item) => ({ id: item.export_id, exportId: item.export_id, title: humanize(item.export_type), status: item.status, statusTone: exportTone(item.status), createdAt: formatDateTime(item.created_at_utc ?? item.requested_at_utc), primaryAction: item.status === "ready" ? "download" as const : item.status === "failed" || item.status === "expired" ? "retry" as const : "view" as const }));
  return [{ id: "exports", title: "Defense packets and exports", items }];
}

export function buildTimelineItems(incident: IncidentDetail, workspace?: CaseWorkspaceResponse | null): TimelineItem[] {
  const eventItems = incident.timeline.map((event, index) => ({ id: `event-${index}-${event.occurred_at_utc}`, title: humanize(event.event_type), timestamp: formatDateTime(event.occurred_at_utc), absolute: event.occurred_at_utc, actor: humanize(event.actor_type), description: "Case event recorded.", technical: JSON.stringify(event.payload ?? {}, null, 2) }));
  const activityItems = (workspace?.activity ?? []).map((item, index) => ({ id: `activity-${index}-${item.occurred_at_utc}`, title: humanize(item.type), timestamp: formatDateTime(item.occurred_at_utc), absolute: item.occurred_at_utc, actor: item.actor_id ? `${humanize(item.actor_type)} ${shortId(item.actor_id)}` : humanize(item.actor_type), description: humanize(item.source), technical: JSON.stringify(item.detail ?? {}, null, 2) }));
  return [...eventItems, ...activityItems].sort((a, b) => new Date(b.absolute).getTime() - new Date(a.absolute).getTime());
}

export function selectNextAction(missingItems: string[], blockers: ReturnType<typeof groupBlockers>, exports: ExportSummary[], readiness: string): NextAction {
  const ready = exports.find((item) => item.status === "ready");
  if (ready) return { label: "Download defense packet", reason: "A generated packet is ready for review or delivery.", kind: "download" };
  if (blockers.critical.length > 0) return { label: "Review blockers", reason: blockers.critical[0]?.message ?? "Critical readiness blockers require review.", kind: "blockers" };
  if (missingItems.length > 0) return { label: "Request missing evidence", reason: `${missingItems[0]} is still needed for defense readiness.`, kind: "missing_evidence" };
  if (readiness === "ready_for_export" || readiness === "ready") return { label: "Generate defense packet", reason: "Required evidence is ready for export generation.", kind: "generate" };
  return { label: "Update case", reason: "Review status, assignment, and remaining case details.", kind: "update" };
}

export function buildIncidentWorkspaceViewModel({ incident, workspace, notes, tasks, now = new Date() }: { incident: IncidentDetail; workspace?: CaseWorkspaceResponse | null; notes?: IncidentNoteItem[]; tasks?: IncidentTaskItem[]; now?: Date }): IncidentWorkspaceViewModel {
  const readiness = workspace?.readiness_state ?? incident.readiness_state ?? "not_ready";
  const readinessPercent = workspace?.completeness.percent ?? incident.completeness_percent ?? 0;
  const blockers = groupBlockers((workspace?.blockers as Blocker[] | undefined) ?? incident.blockers ?? []);
  const missingItems = workspace?.missing_items ?? incident.completeness_missing_items ?? [];
  const latestActivity = [...(workspace?.activity ?? []).map((item) => item.occurred_at_utc), ...(incident.timeline ?? []).map((item) => item.occurred_at_utc), incident.created_at_utc].filter(Boolean).sort().at(-1) ?? incident.created_at_utc;
  const ownerLabel = workspace?.owner?.email ?? (workspace?.owner?.user_id ? `User ${shortId(workspace.owner.user_id)}` : "Unassigned");
  return {
    caseReference: caseReference(incident.incident_id),
    title: incident.severity ? `${humanize(incident.severity)} Incident` : "Incident",
    statusLabel: humanize(workspace?.case_status ?? incident.status),
    statusTone: statusTone(workspace?.case_status ?? incident.status),
    readinessLabel: humanize(readiness),
    readinessTone: readinessTone(readiness),
    readinessPercent,
    createdLabel: formatDateTime(incident.created_at_utc),
    createdAbsolute: incident.created_at_utc ?? "",
    updatedLabel: relativeTime(latestActivity, now),
    location: "Location not recorded",
    ownerLabel,
    driverLabel: incident.adc_driver_id ? `Driver ${shortId(incident.adc_driver_id)}` : "Driver not recorded",
    vehicleLabel: incident.adc_vehicle_id ?? incident.samsara_vehicle_id ? `Vehicle ${incident.adc_vehicle_id ?? incident.samsara_vehicle_id}` : "Vehicle not recorded",
    narrative: `${humanize(incident.severity)} incident opened ${formatDateTime(incident.created_at_utc)}. Current case status is ${humanize(workspace?.case_status ?? incident.status)} with ${readinessPercent}% evidence readiness.`,
    blockers,
    missingItems,
    evidenceGroups: buildEvidenceGroups(incident.evidence_inventory),
    documentGroups: buildDocumentGroups(incident.export_status),
    timelineItems: buildTimelineItems(incident, workspace),
    activityItems: [ ...(notes ?? []).map((note) => ({ id: note.note_id, title: humanize(note.note_type), timestamp: formatDateTime(note.created_at_utc), body: note.body, actor: note.created_by_user_id ? `User ${shortId(note.created_by_user_id)}` : "Case note", kind: "note" as const })), ...(tasks ?? []).map((task) => ({ id: task.task_id, title: task.title, timestamp: formatDateTime(task.created_at_utc), body: `${humanize(task.status)} · ${humanize(task.priority)} priority`, actor: task.assigned_to_user_id ? `Assigned to ${shortId(task.assigned_to_user_id)}` : "Task", kind: "task" as const, taskStatus: task.status })) ],
    nextAction: selectNextAction(missingItems, blockers, incident.export_status, readiness),
  };
}
