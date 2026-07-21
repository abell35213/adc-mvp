import type { CaseOpsAlerts, CaseOpsQueueItem, CaseOpsSummaryMetrics, CaseTaskWidgetItem } from "@/lib/api";

const TERMINAL_STATUSES = new Set(["closed"]);

export function shortCaseId(id: string) {
  return id ? `Case ${id.slice(0, 8)}` : "Case unavailable";
}

export function caseLabel(item: Pick<CaseOpsQueueItem, "incident_id">) {
  return shortCaseId(item.incident_id);
}

export function ownerLabel(ownerUserId?: string | null) {
  if (!ownerUserId) return "Unassigned";
  return `User ${ownerUserId.slice(0, 8)}`;
}

export function incidentContext(item: Pick<CaseOpsQueueItem, "adc_vehicle_id" | "adc_driver_id" | "created_at_utc" | "severity">) {
  const vehicle = item.adc_vehicle_id ? `Vehicle ${item.adc_vehicle_id}` : "Vehicle not linked";
  const driver = item.adc_driver_id ? `Driver ${item.adc_driver_id}` : "Driver not linked";
  return { primary: vehicle, secondary: [driver, formatAbsoluteDate(item.created_at_utc), item.severity].filter(Boolean).join(" · ") };
}

export function isActiveCase(item: Pick<CaseOpsQueueItem, "case_status">) {
  return !TERMINAL_STATUSES.has(item.case_status);
}

export function needsAction(item: CaseOpsQueueItem) {
  return item.blockers.critical > 0 || item.blockers.important > 0 || item.case_status === "escalated" || item.case_status === "awaiting_evidence" || item.readiness_state === "not_ready" || item.readiness_state === "blocked";
}

export function readyForExport(item: Pick<CaseOpsQueueItem, "case_status" | "readiness_state">) {
  return item.case_status === "ready_for_export" || item.readiness_state === "ready_for_export" || item.readiness_state === "ready";
}

export function isOverdueTask(task: Pick<CaseTaskWidgetItem, "due_at_utc" | "status">, now = new Date()) {
  if (!task.due_at_utc || task.status === "completed") return false;
  return new Date(task.due_at_utc).getTime() < now.getTime();
}

export function buildOperationalMetrics({
  queue,
  metrics,
  overdueTasks,
}: {
  queue: CaseOpsQueueItem[];
  metrics: CaseOpsSummaryMetrics | null;
  overdueTasks: CaseTaskWidgetItem[];
}) {
  const activeCases = metrics?.open_incidents ?? queue.filter(isActiveCase).length;
  const needAction = metrics?.blocked_incidents ?? queue.filter(needsAction).length;
  const exportReady = queue.filter(readyForExport).length;
  const overdue = metrics?.overdue_tasks ?? overdueTasks.filter((task) => isOverdueTask(task)).length;

  return { activeCases, needAction, exportReady, overdue };
}

export function priorityScore(item: CaseOpsQueueItem) {
  let score = 0;
  if (item.blockers.critical > 0 || item.case_status === "escalated") score += 10_000;
  if (item.readiness_state === "blocked" || item.readiness_state === "not_ready") score += 4_000;
  score += item.blockers.important * 500;
  if (item.case_status === "awaiting_evidence") score += 350;
  if (!item.owner_user_id) score += 150;
  score += Math.max(0, 100 - Math.round(item.completeness_percent));
  const updated = new Date(item.last_activity_at_utc ?? item.created_at_utc ?? 0).getTime();
  return { score, updated };
}

export function sortPriorityCases(items: CaseOpsQueueItem[]) {
  return [...items].sort((a, b) => {
    const aPriority = priorityScore(a);
    const bPriority = priorityScore(b);
    if (bPriority.score !== aPriority.score) return bPriority.score - aPriority.score;
    return bPriority.updated - aPriority.updated;
  });
}

export function formatAbsoluteDate(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" }).format(date);
}

export function formatRelativeTime(value?: string | null, now = new Date()) {
  if (!value) return "Not updated";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not updated";
  const diffMs = date.getTime() - now.getTime();
  const abs = Math.abs(diffMs);
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  const minute = 60_000;
  const hour = 60 * minute;
  const day = 24 * hour;
  if (abs < hour) return rtf.format(Math.round(diffMs / minute), "minute");
  if (abs < day) return rtf.format(Math.round(diffMs / hour), "hour");
  return rtf.format(Math.round(diffMs / day), "day");
}

export type AttentionKey = "critical" | "missingEvidence" | "unassigned" | "overdue" | "exportReady" | "stalled";
export type AttentionFilterPatch = {
  status?: string;
  readiness_state?: string;
  blockers?: string;
  search?: string;
  sort?: "urgency" | "readiness" | "newest";
};
export interface AttentionItem {
  key: AttentionKey;
  label: string;
  count: number;
  explanation: string;
  filter?: AttentionFilterPatch;
}

export function isAttentionFilterActive(filters: AttentionFilterPatch, item: AttentionItem) {
  if (!item.filter) return false;
  return Object.entries(item.filter).every(([key, value]) => filters[key as keyof AttentionFilterPatch] === value);
}

export function buildAttentionItems({ alerts, queue, overdueTasks }: { alerts: CaseOpsAlerts | null; queue: CaseOpsQueueItem[]; overdueTasks: CaseTaskWidgetItem[] }) {
  const counts = {
    critical: queue.filter((item) => item.blockers.critical > 0).length,
    missingEvidence: queue.filter((item) => item.case_status === "awaiting_evidence").length,
    unassigned: alerts?.unassigned ?? queue.filter((item) => !item.owner_user_id).length,
    overdue: alerts?.overdue ?? overdueTasks.length,
    exportReady: queue.filter((item) => item.case_status === "ready_for_export").length,
    stalled: alerts?.stalled ?? 0,
  };
  return [
    { key: "critical" as const, label: "Critical blockers", count: counts.critical, explanation: "Cases blocked by critical evidence.", filter: { blockers: "critical" } },
    { key: "missingEvidence" as const, label: "Missing evidence", count: counts.missingEvidence, explanation: "Cases in the awaiting-evidence queue.", filter: { status: "awaiting_evidence" } },
    { key: "overdue" as const, label: "Overdue follow-ups", count: counts.overdue, explanation: "Follow-up work is past due." },
    { key: "unassigned" as const, label: "Unassigned cases", count: counts.unassigned, explanation: "Ownership is missing." },
    { key: "exportReady" as const, label: "Ready for export", count: counts.exportReady, explanation: "Defense packets can be generated or reviewed.", filter: { status: "ready_for_export" } },
    { key: "stalled" as const, label: "Stalled cases", count: counts.stalled, explanation: "No recent movement and at risk of delay." },
  ] as AttentionItem[];
}
