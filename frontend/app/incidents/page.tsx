"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import MainLayout from "@/components/MainLayout";
import { listIncidents, type Incident } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";

/**
 * Incident listing page.  Displays all incidents accessible to the
 * current user in a table with key metadata and progress indicators.
 * The page is wrapped in the MainLayout to provide a consistent
 * navigation bar.  Admin users see an Admin link in the nav bar via
 * MainLayout.  From each row users can navigate to a detailed view.
 */
export default function IncidentsPage() {
  const { user, loading: authLoading } = useAuth();
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    // Fetch the list of incidents once the user is available.
    if (!user) return;
    listIncidents()
      .then(setIncidents)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [user]);

  function friendlyStatus(s: string): string {
    if (s === "evidence_capturing" || s === "open") return "Capturing Evidence";
    if (s === "ready" || s === "closed" || s === "export_ready") return "Export Ready";
    return "Ready for Export";
  }

  function statusColor(s: string): string {
    if (s === "evidence_capturing" || s === "open")
      return "bg-yellow-100 text-yellow-800";
    if (s === "ready" || s === "closed" || s === "export_ready")
      return "bg-green-100 text-green-800";
    return "bg-blue-100 text-blue-800";
  }

  function formatTime(iso?: string): string {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  return (
    <MainLayout title="Incidents">
      {/* Page header */}
      <div className="mb-4">
        <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">Incidents</h2>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          View and manage all recorded incidents.  Monitor evidence capture and export status.
        </p>
      </div>

      {/* Loading and error states */}
      {(loading || authLoading) && <p className="text-gray-500">Loading…</p>}
      {error && <p className="text-red-600">{error}</p>}

      {/* No incidents */}
      {!loading && incidents.length === 0 && (
        <p className="text-gray-500">No incidents found.</p>
      )}

      {/* Incident table */}
      {!loading && incidents.length > 0 && (
        <div className="overflow-hidden rounded-lg border bg-white shadow dark:border-gray-700 dark:bg-gray-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 dark:bg-gray-700">
              <tr>
                <th className="px-4 py-3 font-medium text-gray-700 dark:text-gray-300">Incident ID</th>
                <th className="px-4 py-3 font-medium text-gray-700 dark:text-gray-300">Created</th>
                <th className="px-4 py-3 font-medium text-gray-700 dark:text-gray-300">Vehicle</th>
                <th className="px-4 py-3 font-medium text-gray-700 dark:text-gray-300">Status</th>
                <th className="px-4 py-3 font-medium text-gray-700 dark:text-gray-300">Evidence</th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-gray-700">
              {incidents.map((inc) => {
                const captured = inc.evidence_captured ?? 0;
                const total = inc.evidence_total ?? 0;
                const pct = total > 0 ? Math.round((captured / total) * 100) : 0;
                return (
                  <tr
                    key={inc.incident_id}
                    className="hover:bg-gray-50 dark:hover:bg-gray-750"
                  >
                    <td className="px-4 py-3">
                      <Link
                        href={`/incidents/${inc.incident_id}`}
                        className="font-mono text-blue-600 hover:underline dark:text-blue-400"
                      >
                        {inc.incident_id.slice(0, 8)}…
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                      {formatTime(inc.created_at_utc)}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">
                      {inc.adc_vehicle_id ?? "—"}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(
                          inc.status
                        )}`}
                      >
                        {friendlyStatus(inc.status)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="h-2 w-20 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-600">
                          <div
                            className="h-full rounded-full bg-blue-500"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          {captured}/{total}
                        </span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </MainLayout>
  );
}