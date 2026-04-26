import type { CaseOpsQueueSort } from "@/lib/api";

export interface IncidentFilters {
  status: string;
  readiness_state: string;
  blockers: string;
  search: string;
  sort: CaseOpsQueueSort;
}

interface IncidentFilterBarProps {
  filters: IncidentFilters;
  onChange: (next: IncidentFilters) => void;
  onReset: () => void;
}

export default function IncidentFilterBar({
  filters,
  onChange,
  onReset,
}: IncidentFilterBarProps) {
  return (
    <section className="rounded-lg border border-border-default bg-surface p-4 shadow-card">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-text-primary">Filter toolbar</h3>
        <button
          type="button"
          onClick={onReset}
          className="rounded border border-border-default px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-surface-raised"
        >
          Reset filters
        </button>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <input
          value={filters.search}
          onChange={(e) => onChange({ ...filters, search: e.target.value })}
          placeholder="Search incident, vehicle, driver"
          className="rounded border border-border-default bg-surface px-3 py-2 text-sm"
        />
        <select
          value={filters.status}
          onChange={(e) => onChange({ ...filters, status: e.target.value })}
          className="rounded border border-border-default bg-surface px-3 py-2 text-sm"
        >
          <option value="">All statuses</option>
          <option value="new">New</option>
          <option value="awaiting_evidence">Awaiting evidence</option>
          <option value="in_review">In review</option>
          <option value="ready_for_export">Ready for export</option>
          <option value="awaiting_follow_up">Awaiting follow-up</option>
          <option value="escalated">Escalated</option>
          <option value="exported">Exported</option>
          <option value="closed">Closed</option>
        </select>
        <select
          value={filters.readiness_state}
          onChange={(e) => onChange({ ...filters, readiness_state: e.target.value })}
          className="rounded border border-border-default bg-surface px-3 py-2 text-sm"
        >
          <option value="">Any readiness</option>
          <option value="ready">Ready</option>
          <option value="blocked">Blocked</option>
          <option value="not_ready">Not ready</option>
        </select>
        <select
          value={filters.blockers}
          onChange={(e) => onChange({ ...filters, blockers: e.target.value })}
          className="rounded border border-border-default bg-surface px-3 py-2 text-sm"
        >
          <option value="">Any blockers</option>
          <option value="critical">Critical</option>
          <option value="important">Important</option>
          <option value="none">No blockers</option>
        </select>
        <select
          value={filters.sort}
          onChange={(e) => onChange({ ...filters, sort: e.target.value as CaseOpsQueueSort })}
          className="rounded border border-border-default bg-surface px-3 py-2 text-sm"
        >
          <option value="urgency">Sort: Urgency</option>
          <option value="newest">Sort: Newest</option>
          <option value="readiness">Sort: Readiness</option>
        </select>
      </div>
    </section>
  );
}
