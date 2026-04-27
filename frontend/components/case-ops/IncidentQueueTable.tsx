import Link from "next/link";
import type { CaseOpsQueueItem, CaseStatus } from "@/lib/api";
import { CASE_STATUS_META, getCaseStatusMeta, getReadinessMeta } from "@/lib/status";

type QueueTabKey = "all" | "new" | "in_review" | "awaiting_evidence" | "ready_for_export" | "escalated" | "awaiting_follow_up" | "exported" | "closed";

interface QueueTab {
  key: QueueTabKey;
  label: string;
  count: number;
}

interface IncidentQueueTableProps {
  items: CaseOpsQueueItem[];
  loading: boolean;
  error: string;
  tabs: QueueTab[];
  activeTab: QueueTabKey;
  onTabChange: (tab: QueueTabKey) => void;
  onOpen: (incidentId: string) => void;
  onAssignMe: (incidentId: string) => void;
  onCaseStatusChange: (incidentId: string, caseStatus: CaseStatus) => void;
}

const STATUSES: CaseStatus[] = [
  "new",
  "awaiting_evidence",
  "in_review",
  "ready_for_export",
  "awaiting_follow_up",
  "escalated",
  "exported",
  "closed",
];

function getUrgencyTone(item: CaseOpsQueueItem) {
  if (item.blockers.critical > 0 || item.case_status === "escalated") {
    return {
      row: "border-l-4 border-status-critical bg-status-critical-soft/40",
      badge: "bg-status-critical-soft text-status-critical",
      label: "First priority",
    };
  }

  if (item.case_status === "new" || item.blockers.important > 0 || item.readiness_state === "not_ready") {
    return {
      row: "border-l-4 border-status-warning bg-status-warning-soft/40",
      badge: "bg-status-warning-soft text-status-warning",
      label: "Needs attention",
    };
  }

  return {
    row: "border-l-4 border-transparent",
    badge: "bg-status-success-soft text-status-success",
    label: "On track",
  };
}

export default function IncidentQueueTable({
  items,
  loading,
  error,
  tabs,
  activeTab,
  onTabChange,
  onOpen,
  onAssignMe,
  onCaseStatusChange,
}: IncidentQueueTableProps) {
  return (
    <section className="rounded-lg border border-border-default bg-surface shadow-card">
      <div className="border-b border-border-subtle px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          {tabs.map((tab) => {
            const active = tab.key === activeTab;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => onTabChange(tab.key)}
                className={[
                  "rounded-md px-3 py-1.5 text-sm font-medium transition",
                  active
                    ? "bg-status-info-soft text-status-info"
                    : "border border-border-subtle text-text-secondary hover:bg-surface-raised",
                ].join(" ")}
              >
                {tab.label} <span className="ml-1 text-xs">({tab.count})</span>
              </button>
            );
          })}
        </div>
      </div>

      {loading ? <div className="p-4 text-sm text-text-secondary">Loading incident queue…</div> : null}
      {!loading && error ? <div className="m-4 rounded-md border border-status-critical/40 bg-status-critical-soft px-3 py-2 text-sm text-status-critical">{error}</div> : null}
      {!loading && !error && items.length === 0 ? (
        <div className="p-4 text-sm text-text-secondary">No incidents match current filters.</div>
      ) : null}

      {!loading && !error && items.length > 0 ? (
        <div className="max-h-[620px] overflow-auto">
          <table className="w-full min-w-[980px] text-left text-sm">
            <thead className="sticky top-0 z-10 bg-surface-raised">
              <tr>
                <th className="px-3 py-2">Priority</th>
                <th className="px-3 py-2">Incident</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Readiness</th>
                <th className="px-3 py-2">Owner</th>
                <th className="px-3 py-2">Blockers</th>
                <th className="px-3 py-2">Completeness</th>
                <th className="px-3 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const urgency = getUrgencyTone(item);
                return (
                  <tr key={item.incident_id} className={`border-t border-border-subtle ${urgency.row}`}>
                    <td className="px-3 py-3">
                      <span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${urgency.badge}`}>
                        {urgency.label}
                      </span>
                    </td>
                    <td className="px-3 py-3 font-mono text-xs">
                      <Link href={`/incidents/${item.incident_id}`} className="font-semibold text-status-info hover:underline">
                        {item.incident_id.slice(0, 8)}…
                      </Link>
                      <div className="text-text-secondary">{item.adc_vehicle_id ?? "—"} / {item.adc_driver_id ?? "—"}</div>
                    </td>
                    <td className="px-3 py-3 text-text-primary">{getCaseStatusMeta(item.case_status).label}</td>
                    <td className="px-3 py-3 text-text-primary">{getReadinessMeta(item.readiness_state).label}</td>
                    <td className="px-3 py-3 font-mono text-xs text-text-primary">{item.owner_user_id ? item.owner_user_id.slice(0, 8) : "Unassigned"}</td>
                    <td className="px-3 py-3 text-text-primary">{item.blockers.critical} critical · {item.blockers.important} important</td>
                    <td className="px-3 py-3 text-text-primary">{Math.round(item.completeness_percent)}%</td>
                    <td className="px-3 py-3">
                      <div className="flex flex-wrap gap-2">
                        <button type="button" onClick={() => onOpen(item.incident_id)} className="rounded bg-status-info px-2 py-1 text-xs font-medium text-white hover:opacity-90">Open</button>
                        <button type="button" onClick={() => onAssignMe(item.incident_id)} className="rounded border border-border-default px-2 py-1 text-xs text-text-secondary hover:bg-surface-raised">Assign me</button>
                        <select
                          value={item.case_status}
                          onChange={(e) => onCaseStatusChange(item.incident_id, e.target.value as CaseStatus)}
                          className="rounded border border-border-default bg-surface px-2 py-1 text-xs"
                        >
                          {STATUSES.map((status) => (
                            <option key={status} value={status}>{CASE_STATUS_META[status].label}</option>
                          ))}
                        </select>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

export type { QueueTabKey };
