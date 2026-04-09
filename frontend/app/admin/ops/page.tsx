"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AdminLayout from "@/components/AdminLayout";
import {
  FailedJobsTable,
  IntegrationHealthPanel,
  SecurityAnomaliesPanel,
} from "@/components/ops";
import { getOpsDashboard, type OpsDashboardResponse } from "@/lib/api";

export default function OpsDashboardPage() {
  const [data, setData] = useState<OpsDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getOpsDashboard()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load ops dashboard"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <AdminLayout title="Ops Dashboard">
      {loading && <p className="text-sm text-gray-500">Loading…</p>}
      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      {data && (
        <div className="space-y-6">
          <section className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
              <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-100">Stuck Incidents</h2>
              <ul className="mt-2 space-y-2 text-xs text-gray-600 dark:text-gray-300">
                {data.stuck_incidents.map((item) => (
                  <li key={item.incident_id} className="rounded border p-2 dark:border-gray-700">
                    <p className="font-mono">{item.incident_id}</p>
                    <p>{item.reason}</p>
                  </li>
                ))}
                {data.stuck_incidents.length === 0 && <li>None found.</li>}
              </ul>
            </div>

            <div className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
              <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-100">Missing Evidence</h2>
              <ul className="mt-2 space-y-2 text-xs text-gray-600 dark:text-gray-300">
                {data.missing_evidence_incidents.map((item) => (
                  <li key={item.incident_id} className="rounded border p-2 dark:border-gray-700">
                    <p className="font-mono">{item.incident_id}</p>
                    <p>{item.reason}</p>
                  </li>
                ))}
                {data.missing_evidence_incidents.length === 0 && <li>None found.</li>}
              </ul>
            </div>
          </section>

          <FailedJobsTable rows={data.failed_notifications} />

          <section className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-100">Failed Exports</h2>
              <Link href="/exports" className="text-xs text-blue-600 hover:underline">Open exports</Link>
            </div>
            <ul className="space-y-2 text-xs text-gray-600 dark:text-gray-300">
              {data.failed_exports.map((exp) => (
                <li key={exp.export_id} className="rounded border p-2 dark:border-gray-700">
                  <p>
                    Export <span className="font-mono">{exp.export_id}</span> · Incident <span className="font-mono">{exp.incident_id}</span>
                  </p>
                  <p className="text-red-600">{exp.error_message ?? "Unknown export error"}</p>
                </li>
              ))}
              {data.failed_exports.length === 0 && <li>No failed exports.</li>}
            </ul>
          </section>

          <IntegrationHealthPanel items={data.integration_health} />
          <SecurityAnomaliesPanel items={data.recent_anomalies} />
        </div>
      )}
    </AdminLayout>
  );
}
