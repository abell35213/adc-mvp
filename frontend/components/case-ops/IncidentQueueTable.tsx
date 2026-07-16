import type { CaseOpsQueueItem, CaseStatus } from "@/lib/api";
import { Button, Card, CardContent, CardHeader, DropdownMenu, EmptyState, ProgressBar, Skeleton, StatusBadge, TableContainer, Avatar } from "@/components/ui";
import { CASE_STATUS_META, getCaseStatusMeta } from "@/lib/status";
import { caseLabel, formatAbsoluteDate, formatRelativeTime, incidentContext, ownerLabel, sortPriorityCases } from "@/lib/commandCenter";

type QueueTabKey = "all" | "new" | "in_review" | "awaiting_evidence" | "ready_for_export" | "escalated" | "awaiting_follow_up" | "exported" | "closed";

interface QueueTab { key: QueueTabKey; label: string; count: number; }

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
  onCopyCaseId?: (incidentId: string) => void;
}

const STATUSES: CaseStatus[] = ["new", "awaiting_evidence", "in_review", "ready_for_export", "awaiting_follow_up", "escalated", "exported", "closed"];

function readinessContext(item: CaseOpsQueueItem) {
  if (item.blockers.critical > 0) return `${item.blockers.critical} critical items missing`;
  if (item.blockers.important > 0) return `${item.blockers.important} important items missing`;
  if (item.case_status === "ready_for_export") return "Defense packet can be generated";
  return "Evidence readiness";
}

function QueueRow({ item, onOpen, onAssignMe, onCaseStatusChange, onCopyCaseId }: Omit<IncidentQueueTableProps, "items" | "loading" | "error" | "tabs" | "activeTab" | "onTabChange"> & { item: CaseOpsQueueItem }) {
  const status = getCaseStatusMeta(item.case_status);
  const incident = incidentContext(item);
  const owner = ownerLabel(item.owner_user_id);
  const updatedAt = item.last_activity_at_utc ?? item.created_at_utc ?? null;
  const absoluteUpdated = formatAbsoluteDate(updatedAt);
  const menuItems = [
    { label: "Assign to me", onSelect: () => onAssignMe(item.incident_id), disabled: Boolean(item.owner_user_id) },
    ...STATUSES.filter((statusOption) => statusOption !== item.case_status).map((statusOption) => ({ label: `Set ${CASE_STATUS_META[statusOption].label}`, onSelect: () => onCaseStatusChange(item.incident_id, statusOption) })),
    { label: "Copy case ID", onSelect: () => onCopyCaseId?.(item.incident_id), separatorBefore: true },
  ];

  return (
    <tr className="border-t border-border-subtle hover:bg-surface-subtle/60">
      <td className="px-4 py-4 align-top">
        <div className="font-semibold text-text-primary">{caseLabel(item)}</div>
        <div className="mt-1 max-w-52 truncate text-xs text-text-muted" title={item.incident_id}>Technical ID available in actions</div>
      </td>
      <td className="px-4 py-4 align-top">
        <div className="font-medium text-text-primary">{incident.primary}</div>
        <div className="mt-1 text-xs text-text-secondary">{incident.secondary || "Incident details pending"}</div>
      </td>
      <td className="px-4 py-4 align-top"><StatusBadge tone={status.tone} dot>{status.label}</StatusBadge></td>
      <td className="px-4 py-4 align-top"><ProgressBar label={`Readiness for ${caseLabel(item)}`} value={Math.round(item.completeness_percent)} tone={item.completeness_percent >= 80 ? "success" : item.blockers.critical > 0 ? "critical" : "warning"} /><p className="mt-1 text-xs text-text-secondary">{readinessContext(item)}</p></td>
      <td className="px-4 py-4 align-top"><div className="flex items-center gap-2"><Avatar name={owner} size="sm"/><span className="text-sm text-text-primary">{owner}</span></div></td>
      <td className="px-4 py-4 align-top"><time dateTime={updatedAt ?? undefined} title={absoluteUpdated || undefined} className="text-sm text-text-secondary">{formatRelativeTime(updatedAt)}</time><span className="sr-only"> {absoluteUpdated}</span></td>
      <td className="px-4 py-4 align-top"><div className="flex items-center gap-2"><Button size="sm" onClick={() => onOpen(item.incident_id)} aria-label={`Open case ${caseLabel(item)}`}>Open case</Button><DropdownMenu label="More" items={menuItems}/></div></td>
    </tr>
  );
}

function MobileCaseCard(props: Parameters<typeof QueueRow>[0]) {
  const { item, onOpen } = props;
  const status = getCaseStatusMeta(item.case_status);
  const incident = incidentContext(item);
  const owner = ownerLabel(item.owner_user_id);
  return (
    <Card variant="subtle" className="md:hidden">
      <CardContent className="space-y-4">
        <div className="flex items-start justify-between gap-3"><div><h3 className="font-semibold text-text-primary">{caseLabel(item)}</h3><p className="mt-1 text-sm text-text-secondary">{incident.primary}</p><p className="text-xs text-text-muted">{incident.secondary}</p></div><StatusBadge tone={status.tone} dot>{status.label}</StatusBadge></div>
        <ProgressBar label={`Readiness for ${caseLabel(item)}`} value={Math.round(item.completeness_percent)} tone={item.completeness_percent >= 80 ? "success" : item.blockers.critical > 0 ? "critical" : "warning"}/>
        <div className="grid gap-2 text-sm text-text-secondary"><div>Owner: <span className="text-text-primary">{owner}</span></div><div>Updated: <time dateTime={item.last_activity_at_utc ?? item.created_at_utc ?? undefined} title={formatAbsoluteDate(item.last_activity_at_utc ?? item.created_at_utc)}>{formatRelativeTime(item.last_activity_at_utc ?? item.created_at_utc)}</time></div></div>
        <div className="flex gap-2"><Button size="sm" onClick={() => onOpen(item.incident_id)} aria-label={`Open case ${caseLabel(item)}`}>Open case</Button><DropdownMenu label="More" items={[{ label: "Assign to me", onSelect: () => props.onAssignMe(item.incident_id), disabled: Boolean(item.owner_user_id) }, { label: "Copy case ID", onSelect: () => props.onCopyCaseId?.(item.incident_id) }]}/></div>
      </CardContent>
    </Card>
  );
}

export default function IncidentQueueTable({ items, loading, error, tabs, activeTab, onTabChange, onOpen, onAssignMe, onCaseStatusChange, onCopyCaseId }: IncidentQueueTableProps) {
  const sortedItems = sortPriorityCases(items);
  return (
    <Card className="overflow-visible">
      <CardHeader title="Priority Case Queue" description="Cases are ordered by blockers, readiness risk, ownership, and latest activity." />
      <div className="border-b border-border-subtle px-5 py-3"><div className="flex flex-wrap gap-2" aria-label="Queue status filters">{tabs.map((tab) => <Button key={tab.key} variant={tab.key === activeTab ? "primary" : "secondary"} size="sm" onClick={() => onTabChange(tab.key)}>{tab.label} <span className="text-xs">({tab.count})</span></Button>)}</div></div>
      {loading ? <CardContent><div className="space-y-3" aria-live="polite" aria-label="Loading priority cases">{Array.from({ length: 5 }).map((_, index) => <Skeleton key={index} className="h-16" />)}</div></CardContent> : null}
      {!loading && error ? <CardContent><EmptyState title="Priority queue unavailable" message={error} /></CardContent> : null}
      {!loading && !error && sortedItems.length === 0 ? <CardContent><EmptyState title="No cases match these filters" message="Clear filters or broaden your search to return to the active queue." /></CardContent> : null}
      {!loading && !error && sortedItems.length > 0 ? <><div className="hidden md:block"><TableContainer caption="Priority cases"><thead className="bg-surface-subtle"><tr><th scope="col" className="px-4 py-3 text-left text-xs font-medium text-text-secondary">Case</th><th scope="col" className="px-4 py-3 text-left text-xs font-medium text-text-secondary">Incident</th><th scope="col" className="px-4 py-3 text-left text-xs font-medium text-text-secondary">Status</th><th scope="col" className="px-4 py-3 text-left text-xs font-medium text-text-secondary">Readiness</th><th scope="col" className="px-4 py-3 text-left text-xs font-medium text-text-secondary">Owner</th><th scope="col" className="px-4 py-3 text-left text-xs font-medium text-text-secondary">Updated</th><th scope="col" className="px-4 py-3 text-left text-xs font-medium text-text-secondary">Actions</th></tr></thead><tbody>{sortedItems.map((item) => <QueueRow key={item.incident_id} item={item} onOpen={onOpen} onAssignMe={onAssignMe} onCaseStatusChange={onCaseStatusChange} onCopyCaseId={onCopyCaseId}/>)}</tbody></TableContainer></div><div className="space-y-3 p-4 md:hidden">{sortedItems.map((item) => <MobileCaseCard key={item.incident_id} item={item} onOpen={onOpen} onAssignMe={onAssignMe} onCaseStatusChange={onCaseStatusChange} onCopyCaseId={onCopyCaseId}/>)}</div></> : null}
    </Card>
  );
}

export type { QueueTabKey };
