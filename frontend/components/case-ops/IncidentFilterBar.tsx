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
    <section className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <div className="grid gap-3 md:grid-cols-5">
        <input
          value={filters.search}
          onChange={(e) => onChange({ ...filters, search: e.target.value })}
          placeholder="Search incident, vehicle, driver"
          className="rounded border px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-900"
        />
        <select
          value={filters.status}
          onChange={(e) => onChange({ ...filters, status: e.target.value })}
          className="rounded border px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-900"
        >
          <option value="">All statuses</option>
          <option value="new">New</option>
          <option value="awaiting_evidence">Awaiting evidence</option>
          <option value="in_review">In review</option>
          <option value="ready_for_export">Ready for export</option>
          <option value="escalated">Escalated</option>
          <option value="closed">Closed</option>
        </select>
        <select
          value={filters.readiness_state}
          onChange={(e) => onChange({ ...filters, readiness_state: e.target.value })}
          className="rounded border px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-900"
        >
          <option value="">Any readiness</option>
          <option value="ready">Ready</option>
          <option value="blocked">Blocked</option>
          <option value="not_ready">Not ready</option>
        </select>
        <select
          value={filters.blockers}
          onChange={(e) => onChange({ ...filters, blockers: e.target.value })}
          className="rounded border px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-900"
        >
          <option value="">Any blockers</option>
          <option value="critical">Critical</option>
          <option value="important">Important</option>
          <option value="none">No blockers</option>
        </select>
        <div className="flex gap-2">
          <select
            value={filters.sort}
            onChange={(e) => onChange({ ...filters, sort: e.target.value as CaseOpsQueueSort })}
            className="w-full rounded border px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-900"
          >
            <option value="urgency">Sort: Urgency</option>
            <option value="newest">Sort: Newest</option>
            <option value="readiness">Sort: Readiness</option>
          </select>
          <button
            onClick={onReset}
            className="rounded border px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700"
          >
            Reset
          </button>
        </div>
      </div>
    </section>
  );
}
