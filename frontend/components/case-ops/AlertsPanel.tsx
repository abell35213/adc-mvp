import type { CaseOpsAlerts } from "@/lib/api";

interface AlertsPanelProps {
  alerts: CaseOpsAlerts | null;
  loading: boolean;
  error: string;
}

export default function AlertsPanel({ alerts, loading, error }: AlertsPanelProps) {
  return (
    <section className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Alerts</h3>
      {loading && <p className="mt-2 text-sm text-gray-500">Loading alerts…</p>}
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      {!loading && !error && alerts && (
        <ul className="mt-3 space-y-1 text-sm text-gray-700 dark:text-gray-300">
          <li>Stalled incidents: {alerts.stalled}</li>
          <li>Unassigned incidents: {alerts.unassigned}</li>
          <li>Overdue tasks: {alerts.overdue}</li>
          <li>Blocked incidents: {alerts.blocked}</li>
          <li>Export aging: {alerts.export_aging}</li>
        </ul>
      )}
    </section>
  );
}
