"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  getIncident,
  requestExport,
  type IncidentDetail,
} from "@/lib/api";

export default function IncidentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [incident, setIncident] = useState<IncidentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.replace("/login");
      return;
    }
    getIncident(id)
      .then(setIncident)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id, router]);

  async function handleExport() {
    setExporting(true);
    try {
      await requestExport(id);
      // Refresh to show new export
      const updated = await getIncident(id);
      setIncident(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(false);
    }
  }

  const statusColor = (s: string) => {
    if (s === "pending" || s === "requested") return "bg-yellow-100 text-yellow-800";
    if (s === "ready" || s === "captured") return "bg-green-100 text-green-800";
    if (s === "failed" || s === "unavailable") return "bg-red-100 text-red-800";
    return "bg-gray-100 text-gray-800";
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-gray-500">Loading…</p>
      </div>
    );
  }

  if (error || !incident) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-red-600">{error || "Incident not found"}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="flex items-center justify-between border-b bg-white px-6 py-4 dark:bg-gray-800">
        <div className="flex items-center gap-4">
          <Link
            href="/incidents"
            className="text-sm text-blue-600 hover:underline dark:text-blue-400"
          >
            ← Incidents
          </Link>
          <h1 className="text-lg font-bold text-gray-900 dark:text-white">
            Incident {incident.incident_id.slice(0, 8)}…
          </h1>
        </div>
        <button
          onClick={handleExport}
          disabled={exporting}
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {exporting ? "Requesting…" : "Request Export"}
        </button>
      </header>

      <main className="mx-auto max-w-5xl space-y-6 p-6">
        {/* Summary card */}
        <div className="rounded-lg border bg-white p-6 shadow dark:bg-gray-800">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
            Summary
          </h2>
          <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-gray-500 dark:text-gray-400">Status</dt>
              <dd className="mt-1 font-medium">{incident.status}</dd>
            </div>
            <div>
              <dt className="text-gray-500 dark:text-gray-400">Severity</dt>
              <dd className="mt-1 font-medium capitalize">
                {incident.severity ?? "—"}
              </dd>
            </div>
            <div>
              <dt className="text-gray-500 dark:text-gray-400">Vehicle</dt>
              <dd className="mt-1 font-mono">{incident.adc_vehicle_id ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-gray-500 dark:text-gray-400">Samsara ID</dt>
              <dd className="mt-1 font-mono">
                {incident.samsara_vehicle_id ?? "—"}
              </dd>
            </div>
            <div>
              <dt className="text-gray-500 dark:text-gray-400">Driver</dt>
              <dd className="mt-1 font-mono">{incident.adc_driver_id ?? "—"}</dd>
            </div>
          </dl>
        </div>

        {/* Evidence inventory */}
        <div className="rounded-lg border bg-white p-6 shadow dark:bg-gray-800">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
            Evidence Inventory
          </h2>
          {incident.evidence_inventory.length === 0 ? (
            <p className="text-sm text-gray-400">No artifacts yet.</p>
          ) : (
            <ul className="space-y-2">
              {incident.evidence_inventory.map((a) => (
                <li
                  key={a.artifact_id}
                  className="flex items-center justify-between rounded border px-4 py-2 text-sm"
                >
                  <span className="font-mono text-xs">
                    {a.artifact_type}
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(a.status)}`}
                  >
                    {a.status}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Exports */}
        <div className="rounded-lg border bg-white p-6 shadow dark:bg-gray-800">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
            Exports
          </h2>
          {incident.export_status.length === 0 ? (
            <p className="text-sm text-gray-400">No exports yet.</p>
          ) : (
            <ul className="space-y-2">
              {incident.export_status.map((ex) => (
                <li
                  key={ex.export_id}
                  className="flex items-center justify-between rounded border px-4 py-2 text-sm"
                >
                  <span className="font-mono text-xs">
                    {ex.export_id.slice(0, 8)}…
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(ex.status)}`}
                  >
                    {ex.status}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </main>
    </div>
  );
}
