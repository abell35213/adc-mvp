"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  getIncident,
  requestExport,
  downloadExport,
  type IncidentDetail,
  type ArtifactSummary,
} from "@/lib/api";

/** Canonical evidence types with display labels. */
const EVIDENCE_TYPES: { type: string; label: string }[] = [
  { type: "dashcam_road", label: "Dashcam Road" },
  { type: "dashcam_driver", label: "Dashcam Driver" },
  { type: "eld_duty_status", label: "ELD Duty Status" },
  { type: "gps_trace", label: "GPS Trace" },
  { type: "safety_events", label: "Safety Events" },
  { type: "vehicle_state", label: "Vehicle State" },
  { type: "evidence_inventory", label: "Evidence Inventory" },
  { type: "chain_of_custody", label: "Chain of Custody" },
];

function friendlyEventType(t: string): string {
  return t
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function artifactStatusBadge(status: string) {
  if (status === "captured")
    return "bg-green-100 text-green-800";
  if (status === "unavailable")
    return "bg-red-100 text-red-800";
  if (status === "pending")
    return "bg-yellow-100 text-yellow-800";
  return "bg-gray-100 text-gray-800";
}

function artifactStatusLabel(status: string): string {
  if (status === "captured") return "Captured";
  if (status === "unavailable") return "Unavailable";
  if (status === "pending") return "Pending";
  return status;
}

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
      const updated = await getIncident(id);
      setIncident(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(false);
    }
  }

  async function handleDownload(exportId: string) {
    try {
      const data = await downloadExport(exportId);
      window.open(data.url, "_blank");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Download failed");
    }
  }

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

  // Build evidence map for the inventory table
  const artifactMap = new Map<string, ArtifactSummary>();
  for (const a of incident.evidence_inventory) {
    artifactMap.set(a.artifact_type, a);
  }

  const captured = incident.evidence_inventory.filter(
    (a) => a.status === "captured"
  ).length;
  const total = incident.evidence_inventory.length || EVIDENCE_TYPES.length;

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
          <span className="text-xs text-gray-400">
            {formatTime(incident.created_at_utc)}
          </span>
        </div>
        <span className="text-sm text-gray-500">
          Evidence: {captured}/{total} captured
        </span>
      </header>

      <main className="mx-auto max-w-6xl space-y-6 p-6">
        {/* ── Panel A: Evidence Inventory ────────────────────────── */}
        <div className="rounded-lg border bg-white p-6 shadow dark:bg-gray-800">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
            A) Evidence Inventory
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-gray-50 dark:bg-gray-700">
                <tr>
                  <th className="px-4 py-2 font-medium text-gray-600 dark:text-gray-300">
                    Evidence Type
                  </th>
                  <th className="px-4 py-2 font-medium text-gray-600 dark:text-gray-300">
                    Status
                  </th>
                  <th className="px-4 py-2 font-medium text-gray-600 dark:text-gray-300">
                    Captured Time
                  </th>
                  <th className="px-4 py-2 font-medium text-gray-600 dark:text-gray-300">
                    Reason
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-gray-700">
                {EVIDENCE_TYPES.map(({ type, label }) => {
                  const art = artifactMap.get(type);
                  const status = art?.status ?? "pending";
                  return (
                    <tr key={type}>
                      <td className="px-4 py-2 font-medium text-gray-800 dark:text-gray-200">
                        {label}
                      </td>
                      <td className="px-4 py-2">
                        <span
                          className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${artifactStatusBadge(status)}`}
                        >
                          {artifactStatusLabel(status)}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-gray-500 dark:text-gray-400">
                        {formatTime(art?.captured_at_utc)}
                      </td>
                      <td className="px-4 py-2 text-gray-500 dark:text-gray-400">
                        {art?.unavailable_reason ?? "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* ── Panel B: Timeline ──────────────────────────────────── */}
        <div className="rounded-lg border bg-white p-6 shadow dark:bg-gray-800">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
            B) Timeline
          </h2>
          {(!incident.timeline || incident.timeline.length === 0) ? (
            <p className="text-sm text-gray-400">No events yet.</p>
          ) : (
            <ol className="relative border-l border-gray-200 dark:border-gray-600">
              {incident.timeline.map((ev, i) => (
                <li key={i} className="mb-4 ml-4">
                  <div className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border border-white bg-blue-500 dark:border-gray-800" />
                  <time className="mb-1 text-xs text-gray-400">
                    {formatTime(ev.occurred_at_utc)}
                  </time>
                  <p className="text-sm font-medium text-gray-800 dark:text-gray-200">
                    {friendlyEventType(ev.event_type)}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </div>

        {/* ── Panel C: Export Actions ────────────────────────────── */}
        <div className="rounded-lg border bg-white p-6 shadow dark:bg-gray-800">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
            C) Export Actions
          </h2>
          <div className="mb-4">
            <button
              onClick={handleExport}
              disabled={exporting}
              className="rounded bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {exporting ? "Generating…" : "Generate Court Package"}
            </button>
          </div>
          {incident.export_status.length === 0 ? (
            <p className="text-sm text-gray-400">No exports yet.</p>
          ) : (
            <ul className="space-y-2">
              {incident.export_status.map((ex) => (
                <li
                  key={ex.export_id}
                  className="flex items-center justify-between rounded border px-4 py-3 text-sm"
                >
                  <div>
                    <span className="font-mono text-xs text-gray-600 dark:text-gray-300">
                      {ex.export_id.slice(0, 8)}…
                    </span>
                    <span className="ml-2 text-xs text-gray-400">
                      {formatTime(ex.created_at_utc)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        ex.status === "ready"
                          ? "bg-green-100 text-green-800"
                          : ex.status === "failed"
                            ? "bg-red-100 text-red-800"
                            : "bg-yellow-100 text-yellow-800"
                      }`}
                    >
                      {ex.status}
                    </span>
                    {ex.status === "ready" && (
                      <button
                        onClick={() => handleDownload(ex.export_id)}
                        className="rounded bg-green-600 px-3 py-1 text-xs font-medium text-white hover:bg-green-700"
                      >
                        Download ZIP
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </main>
    </div>
  );
}
