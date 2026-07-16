import type { CaseOpsQueueSort } from "@/lib/api";
import { Button, Card, CardContent, FormField, Input, Select } from "@/components/ui";

export interface IncidentFilters { status: string; readiness_state: string; blockers: string; search: string; sort: CaseOpsQueueSort; }
interface IncidentFilterBarProps { filters: IncidentFilters; onChange: (next: IncidentFilters) => void; onReset: () => void; loading?: boolean; }

export default function IncidentFilterBar({ filters, onChange, onReset, loading = false }: IncidentFilterBarProps) {
  const activeCount = [filters.status, filters.readiness_state, filters.blockers, filters.search].filter(Boolean).length + (filters.sort !== "urgency" ? 1 : 0);
  return (
    <Card variant="subtle">
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2"><div><h2 className="text-sm font-semibold text-text-primary">Filters</h2><p className="text-xs text-text-secondary">Search incident ID, vehicle ID, driver ID, Samsara vehicle ID, or severity returned by the queue API.</p></div><Button variant="secondary" size="sm" onClick={onReset} disabled={loading || activeCount === 0}>Clear filters{activeCount > 0 ? ` (${activeCount})` : ""}</Button></div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <FormField id="dashboard-search" label="Search"><Input id="dashboard-search" value={filters.search} onChange={(e) => onChange({ ...filters, search: e.target.value })} placeholder="Incident, vehicle, driver, severity" disabled={loading}/></FormField>
          <FormField id="dashboard-status" label="Status"><Select id="dashboard-status" value={filters.status} onChange={(e) => onChange({ ...filters, status: e.target.value })} disabled={loading}><option value="">All statuses</option><option value="new">New</option><option value="awaiting_evidence">Awaiting evidence</option><option value="in_review">In review</option><option value="ready_for_export">Ready for export</option><option value="awaiting_follow_up">Awaiting follow-up</option><option value="escalated">Escalated</option><option value="exported">Exported</option><option value="closed">Closed</option></Select></FormField>
          <FormField id="dashboard-readiness" label="Readiness"><Select id="dashboard-readiness" value={filters.readiness_state} onChange={(e) => onChange({ ...filters, readiness_state: e.target.value })} disabled={loading}><option value="">Any readiness</option><option value="ready">Ready</option><option value="ready_for_export">Ready for export</option><option value="blocked">Blocked</option><option value="not_ready">Not ready</option></Select></FormField>
          <FormField id="dashboard-blockers" label="Blockers"><Select id="dashboard-blockers" value={filters.blockers} onChange={(e) => onChange({ ...filters, blockers: e.target.value })} disabled={loading}><option value="">Any blockers</option><option value="critical">Critical</option><option value="important">Important</option><option value="none">No blockers</option></Select></FormField>
          <FormField id="dashboard-sort" label="Sort"><Select id="dashboard-sort" value={filters.sort} onChange={(e) => onChange({ ...filters, sort: e.target.value as CaseOpsQueueSort })} disabled={loading}><option value="urgency">Urgency</option><option value="newest">Newest</option><option value="readiness">Readiness</option></Select></FormField>
        </div>
      </CardContent>
    </Card>
  );
}
