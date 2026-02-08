"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { listIncidents, logout, type Incident } from "@/lib/api";

export default function IncidentsPage() {
  const router = useRouter();
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.replace("/login");
      return;
    }
    listIncidents()
      .then(setIncidents)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [router]);

  const statusColor = (s: string) => {
    if (s === "open" || s === "evidence_capturing") return "bg-yellow-100 text-yellow-800";
    if (s === "ready" || s === "closed") return "bg-green-100 text-green-800";
    return "bg-gray-100 text-gray-800";
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="flex items-center justify-between border-b bg-white px-6 py-4 dark:bg-gray-800">
        <h1 className="text-lg font-bold text-gray-900 dark:text-white">
          ADC Incidents
        </h1>
        <button
          onClick={logout}
          className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400"
        >
          Sign out
        </button>
      </header>

      {/* Content */}
      <main className="mx-auto max-w-5xl p-6">
        {loading && <p className="text-gray-500">Loading…</p>}
        {error && <p className="text-red-600">{error}</p>}

        {!loading && incidents.length === 0 && (
          <p className="text-gray-500">No incidents found.</p>
        )}

        {!loading && incidents.length > 0 && (
          <div className="overflow-hidden rounded-lg border bg-white shadow dark:bg-gray-800">
            <table className="w-full text-left text-sm">
              <thead className="bg-gray-100 dark:bg-gray-700">
                <tr>
                  <th className="px-4 py-3 font-medium text-gray-700 dark:text-gray-300">
                    ID
                  </th>
                  <th className="px-4 py-3 font-medium text-gray-700 dark:text-gray-300">
                    Status
                  </th>
                  <th className="px-4 py-3 font-medium text-gray-700 dark:text-gray-300">
                    Severity
                  </th>
                  <th className="px-4 py-3 font-medium text-gray-700 dark:text-gray-300">
                    Vehicle
                  </th>
                  <th className="px-4 py-3 font-medium text-gray-700 dark:text-gray-300">
                    Driver
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-gray-700">
                {incidents.map((inc) => (
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
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(inc.status)}`}
                      >
                        {inc.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 capitalize">{inc.severity ?? "—"}</td>
                    <td className="px-4 py-3 font-mono text-xs">
                      {inc.adc_vehicle_id ?? "—"}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">
                      {inc.adc_driver_id ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
