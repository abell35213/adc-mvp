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
  const [filter, setFilter] = useState<"all" | "waiting_driver" | "ready">("all");

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

  function isWaitingOnDriver(incident: Incident): boolean {
    const driverResponse = incident.driver_response;
    if (typeof driverResponse?.awaiting_driver_action === "boolean") {
      return driverResponse.awaiting_driver_action;
    }
    const notificationSent = Boolean(driverResponse?.notification_sent_at_utc);
    if (!notificationSent) return false;
    const acknowledged = Boolean(driverResponse?.acknowledged_at_utc);
    const uploadsComplete = Boolean(driverResponse?.uploads_complete);
    return !acknowledged || !uploadsComplete;
  }

  const waitingCount = incidents.filter(isWaitingOnDriver).length;
  const visibleIncidents = incidents.filter((incident) => {
    if (filter === "waiting_driver") return isWaitingOnDriver(incident);
    if (filter === "ready") return !isWaitingOnDriver(incident);
    return true;
  });

  return (
    <MainLayout title="Incidents">
      {/* Page header */}
      <div className="mb-4">
        <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">Incidents</h2>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          View and manage all recorded incidents.  Monitor evidence capture and export status.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            onClick={() => setFilter("all")}
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              filter === "all"
                ? "bg-blue-600 text-white"
                : "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300"
            }`}
          >
            All ({incidents.length})
          </button>
          <button
            onClick={() => setFilter("waiting_driver")}
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              filter === "waiting_driver"
                ? "bg-yellow-500 text-white"
                : "bg-yellow-100 text-yellow-800"
            }`}
          >
            Waiting on driver ({waitingCount})
          </button>
          <button
            onClick={() => setFilter("ready")}
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              filter === "ready"
                ? "bg-green-600 text-white"
                : "bg-green-100 text-green-800"
            }`}
          >
            Driver action complete ({incidents.length - waitingCount})
          </button>
        </div>
      </div>

      {/* Loading and error states */}
      {(loading || authLoading) && <p className="text-gray-500">Loading…</p>}
      {error && <p className="text-red-600">{error}</p>}

      {/* No incidents */}
      {!loading && incidents.length === 0 && (
        <p className="text-gray-500">No incidents found.</p>
      )}
      {!loading && incidents.length > 0 && visibleIncidents.length === 0 && (
        <p className="text-gray-500">No incidents match the selected filter.</p>
      )}

      {/* Incident table */}
      {!loading && visibleIncidents.length > 0 && (
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
              {visibleIncidents.map((inc) => {
                const captured = inc.evidence_captured ?? 0;
                const total = inc.evidence_total ?? 0;
                const pct = total > 0 ? Math.round((captured / total) * 100) : 0;
                const waitingOnDriver = isWaitingOnDriver(inc);
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
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span
                          className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(
                            inc.status
                          )}`}
                        >
                          {friendlyStatus(inc.status)}
                        </span>
                        {waitingOnDriver && (
                          <span className="inline-block rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-800">
                            Waiting on driver
                          </span>
                        )}
                      </div>
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
