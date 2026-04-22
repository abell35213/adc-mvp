import Link from "next/link";
import type { CaseOpsQueueItem } from "@/lib/api";

interface IncidentQueueTableProps {
  items: CaseOpsQueueItem[];
  loading: boolean;
  error: string;
  onOpen: (incidentId: string) => void;
  onAssignMe: (incidentId: string) => void;
  onCaseStatusChange: (incidentId: string, caseStatus: string) => void;
}

const STATUSES = [
  "new",
  "awaiting_evidence",
  "in_review",
  "ready_for_export",
  "escalated",
  "closed",
];

export default function IncidentQueueTable({
  items,
  loading,
  error,
  onOpen,
  onAssignMe,
  onCaseStatusChange,
}: IncidentQueueTableProps) {
  if (loading) {
    return <div className="rounded-lg border bg-white p-4 text-sm text-gray-500 shadow-sm dark:border-gray-700 dark:bg-gray-800">Loading incident queue…</div>;
  }

  if (error) {
    return <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>;
  }

  if (items.length === 0) {
    return <div className="rounded-lg border bg-white p-4 text-sm text-gray-500 shadow-sm dark:border-gray-700 dark:bg-gray-800">No incidents match current filters.</div>;
  }

  return (
    <div className="overflow-hidden rounded-lg border bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <table className="w-full text-left text-sm">
        <thead className="bg-gray-50 dark:bg-gray-700">
          <tr>
            <th className="px-3 py-2">Incident</th>
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2">Readiness</th>
            <th className="px-3 py-2">Owner</th>
            <th className="px-3 py-2">Blockers</th>
            <th className="px-3 py-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.incident_id} className="border-t dark:border-gray-700">
              <td className="px-3 py-3 font-mono text-xs">
                <Link href={`/incidents/${item.incident_id}`} className="text-blue-600 hover:underline dark:text-blue-400">
                  {item.incident_id.slice(0, 8)}…
                </Link>
                <div className="text-gray-500">{item.adc_vehicle_id ?? "—"} / {item.adc_driver_id ?? "—"}</div>
              </td>
              <td className="px-3 py-3">{item.case_status}</td>
              <td className="px-3 py-3">{item.readiness_state}</td>
              <td className="px-3 py-3 font-mono text-xs">{item.owner_user_id ? item.owner_user_id.slice(0, 8) : "Unassigned"}</td>
              <td className="px-3 py-3">{item.blockers.critical} critical · {item.blockers.important} important</td>
              <td className="px-3 py-3">
                <div className="flex flex-wrap gap-2">
                  <button onClick={() => onOpen(item.incident_id)} className="rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700">Open</button>
                  <button onClick={() => onAssignMe(item.incident_id)} className="rounded border px-2 py-1 text-xs hover:bg-gray-100 dark:border-gray-600 dark:hover:bg-gray-700">Assign me</button>
                  <select
                    value={item.case_status}
                    onChange={(e) => onCaseStatusChange(item.incident_id, e.target.value)}
                    className="rounded border px-2 py-1 text-xs dark:border-gray-600 dark:bg-gray-900"
                  >
                    {STATUSES.map((status) => (
                      <option key={status} value={status}>{status}</option>
                    ))}
                  </select>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
