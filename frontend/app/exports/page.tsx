"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import MainLayout from "@/components/MainLayout";
import {
  listExports,
  downloadExport,
  getExport,
  getExportContents,
  getExportDownloadHistory,
  type ExportContentsItem,
  type ExportListItem,
  type ExportSummary,
  type ExportContentsResponse,
  type ExportDownloadAuditResponse,
  type ExportStatus,
  type ExportType,
} from "@/lib/api";
import { getExportStatusBadgeClass, getExportStatusLabel } from "@/lib/exportStatus";

interface ExportFilters {
  incident: string;
  status: "all" | ExportStatus;
  exportType: "all" | ExportType;
  requestedBy: string;
  createdFrom: string;
  createdTo: string;
}

const DEFAULT_FILTERS: ExportFilters = {
  incident: "",
  status: "all",
  exportType: "all",
  requestedBy: "",
  createdFrom: "",
  createdTo: "",
};

function formatDateTime(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

function formatDuration(seconds?: number | null) {
  if (seconds == null) return "—";
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}m ${remainingSeconds}s`;
}

function formatBytes(size?: number | null) {
  if (size == null || size < 0) return "—";
  if (size < 1024) return `${size} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = size / 1024;
  let unitIdx = 0;
  while (value >= 1024 && unitIdx < units.length - 1) {
    value /= 1024;
    unitIdx += 1;
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[unitIdx]}`;
}

function requestedByLabel(ex: ExportListItem | ExportSummary) {
  return ex.requested_by_user_id ?? ex.generated_by ?? "system";
}

export default function ExportsPage() {
  const [exports, setExports] = useState<ExportListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState<ExportFilters>(DEFAULT_FILTERS);
  const [selectedExportId, setSelectedExportId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ExportSummary | null>(null);
  const [contents, setContents] = useState<ExportContentsResponse | null>(null);
  const [audit, setAudit] = useState<ExportDownloadAuditResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    listExports()
      .then(setExports)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedExportId) return;
    Promise.all([
      getExport(selectedExportId),
      getExportContents(selectedExportId),
      getExportDownloadHistory(selectedExportId),
    ])
      .then(([exportDetail, exportContents, exportAudit]) => {
        setDetail(exportDetail);
        setContents(exportContents);
        setAudit(exportAudit);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load export detail");
      })
      .finally(() => setDetailLoading(false));
  }, [selectedExportId]);

  const filteredExports = useMemo(() => {
    return exports.filter((ex) => {
      const incidentMatch =
        !filters.incident ||
        ex.incident_id.toLowerCase().includes(filters.incident.toLowerCase());
      const statusMatch = filters.status === "all" || ex.status === filters.status;
      const typeMatch = filters.exportType === "all" || ex.export_type === filters.exportType;
      const requestedByMatch =
        !filters.requestedBy ||
        requestedByLabel(ex).toLowerCase().includes(filters.requestedBy.toLowerCase());

      const createdAt = ex.created_at_utc ? new Date(ex.created_at_utc) : null;
      const fromMatch = !filters.createdFrom || (createdAt ? createdAt >= new Date(filters.createdFrom) : false);
      const toMatch = !filters.createdTo || (createdAt ? createdAt <= new Date(`${filters.createdTo}T23:59:59`) : false);

      return incidentMatch && statusMatch && typeMatch && requestedByMatch && fromMatch && toMatch;
    });
  }, [exports, filters]);

  const statusOptions = useMemo(
    () => ["all", ...Array.from(new Set(exports.map((ex) => ex.status)))],
    [exports]
  );
  const typeOptions = useMemo(
    () => ["all", ...Array.from(new Set(exports.map((ex) => ex.export_type)))],
    [exports]
  );

  const included = contents?.file_manifest.filter((item) => item.classification === "included") ?? [];
  const excluded =
    contents?.file_manifest.filter((item) => item.classification === "excluded_by_option") ?? [];
  const unavailable =
    contents?.file_manifest.filter((item) =>
      item.classification === "unavailable" || item.classification === "failed_to_retrieve"
    ) ?? [];

  async function handleDownload(exportId: string) {
    try {
      const result = await downloadExport(exportId);
      window.open(result.url, "_blank");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Download failed");
    }
  }

  function updateFilter<K extends keyof ExportFilters>(key: K, value: ExportFilters[K]) {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }

  function openDetail(exportId: string) {
    setDetailLoading(true);
    setError("");
    setSelectedExportId(exportId);
  }

  function renderManifest(items: ExportContentsItem[]) {
    if (items.length === 0) return <p className="text-sm text-gray-500">None</p>;
    return (
      <ul className="space-y-1 text-sm text-gray-700 dark:text-gray-300">
        {items.map((item) => (
          <li key={`${item.kind}-${item.path ?? item.item ?? ""}`} className="rounded border px-2 py-1 dark:border-gray-700">
            <p className="font-medium">{item.item ?? item.kind}</p>
            <p className="text-xs text-gray-500">
              {item.reason ?? "—"} · {formatBytes(item.byte_size)}
            </p>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <MainLayout title="Exports">
      <div className="mb-4">
        <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">Exports</h2>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Export history with filters, package health, and detailed audit/download visibility.
        </p>
      </div>

      <div className="mb-4 grid grid-cols-1 gap-3 rounded-lg border bg-white p-3 shadow dark:border-gray-700 dark:bg-gray-800 md:grid-cols-6">
        <input
          className="rounded border px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-900"
          placeholder="Incident"
          value={filters.incident}
          onChange={(e) => updateFilter("incident", e.target.value)}
        />
        <select
          className="rounded border px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-900"
          value={filters.status}
          onChange={(e) => updateFilter("status", e.target.value as ExportFilters["status"])}
        >
          {statusOptions.map((status) => (
            <option key={status} value={status}>
              {status}
            </option>
          ))}
        </select>
        <select
          className="rounded border px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-900"
          value={filters.exportType}
          onChange={(e) => updateFilter("exportType", e.target.value as ExportFilters["exportType"])}
        >
          {typeOptions.map((exportType) => (
            <option key={exportType} value={exportType}>
              {exportType}
            </option>
          ))}
        </select>
        <input
          className="rounded border px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-900"
          placeholder="Requested by"
          value={filters.requestedBy}
          onChange={(e) => updateFilter("requestedBy", e.target.value)}
        />
        <input
          className="rounded border px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-900"
          type="date"
          value={filters.createdFrom}
          onChange={(e) => updateFilter("createdFrom", e.target.value)}
        />
        <input
          className="rounded border px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-900"
          type="date"
          value={filters.createdTo}
          onChange={(e) => updateFilter("createdTo", e.target.value)}
        />
      </div>

      {loading && <p className="text-gray-500">Loading…</p>}
      {error && <p className="mb-3 text-sm text-red-600">{error}</p>}

      {!loading && filteredExports.length === 0 && <p className="text-gray-500">No exports found.</p>}

      {!loading && filteredExports.length > 0 && (
        <div className="overflow-hidden rounded-lg border bg-white shadow dark:border-gray-700 dark:bg-gray-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 dark:bg-gray-700">
              <tr>
                <th className="px-4 py-3 font-medium">ID</th>
                <th className="px-4 py-3 font-medium">Incident ID</th>
                <th className="px-4 py-3 font-medium">Type</th>
                <th className="px-4 py-3 font-medium">Requested by</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Created</th>
                <th className="px-4 py-3 font-medium">Completed</th>
                <th className="px-4 py-3 font-medium">Download info</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-gray-700">
              {filteredExports.map((ex) => (
                <tr key={ex.export_id}>
                  <td className="px-4 py-3 font-mono text-xs">{ex.export_id.slice(0, 8)}…</td>
                  <td className="px-4 py-3">
                    <Link href={`/incidents/${ex.incident_id}`} className="text-blue-600 hover:underline dark:text-blue-400">
                      {ex.incident_id.slice(0, 8)}…
                    </Link>
                  </td>
                  <td className="px-4 py-3">{ex.export_type}</td>
                  <td className="px-4 py-3">{requestedByLabel(ex)}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${getExportStatusBadgeClass(ex.status)}`}>
                      {getExportStatusLabel(ex.status)}
                    </span>
                  </td>
                  <td className="px-4 py-3">{formatDateTime(ex.created_at_utc)}</td>
                  <td className="px-4 py-3">{formatDateTime(ex.completed_at_utc)}</td>
                  <td className="px-4 py-3 text-xs">
                    <p>Size: {formatBytes(ex.byte_size)}</p>
                    <p>SHA256: {ex.package_sha256 ? `${ex.package_sha256.slice(0, 12)}…` : "—"}</p>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <button
                        onClick={() => openDetail(ex.export_id)}
                        className="rounded bg-gray-700 px-2 py-1 text-xs text-white hover:bg-gray-800"
                      >
                        Details
                      </button>
                      {ex.status === "ready" && (
                        <button
                          onClick={() => handleDownload(ex.export_id)}
                          className="rounded bg-green-600 px-2 py-1 text-xs text-white hover:bg-green-700"
                        >
                          Download
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedExportId && (
        <div className="fixed inset-0 z-40 flex justify-end bg-black/40">
          <aside className="h-full w-full max-w-2xl overflow-y-auto bg-white p-4 shadow-xl dark:bg-gray-900">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold">Export Detail</h3>
              <button
                className="rounded border px-2 py-1 text-sm dark:border-gray-700"
                onClick={() => setSelectedExportId(null)}
              >
                Close
              </button>
            </div>

            {detailLoading && <p className="text-gray-500">Loading detail…</p>}
            {!detailLoading && detail && (
              <div className="space-y-4">
                <section className="rounded border p-3 dark:border-gray-700">
                  <h4 className="mb-2 font-medium">Metadata</h4>
                  <p>ID: {detail.export_id}</p>
                  <p>Incident: {detail.incident_id ?? "—"}</p>
                  <p>Type: {detail.export_type}</p>
                  <p>Status: {getExportStatusLabel(detail.status)}</p>
                  <p>Created: {formatDateTime(detail.created_at_utc)}</p>
                  <p>Completed: {formatDateTime(detail.completed_at_utc)}</p>
                </section>

                <section className="rounded border p-3 dark:border-gray-700">
                  <h4 className="mb-2 font-medium">Request options</h4>
                  <pre className="overflow-auto rounded bg-gray-100 p-2 text-xs dark:bg-gray-800">
                    {JSON.stringify(detail.options_json ?? {}, null, 2)}
                  </pre>
                </section>

                <section className="grid gap-3 rounded border p-3 dark:border-gray-700 md:grid-cols-3">
                  <div>
                    <h4 className="mb-2 font-medium">Included files</h4>
                    {renderManifest(included)}
                  </div>
                  <div>
                    <h4 className="mb-2 font-medium">Excluded files</h4>
                    {renderManifest(excluded)}
                  </div>
                  <div>
                    <h4 className="mb-2 font-medium">Unavailable files</h4>
                    {renderManifest(unavailable)}
                  </div>
                </section>

                <section className="rounded border p-3 dark:border-gray-700">
                  <h4 className="mb-2 font-medium">Checksum + counts</h4>
                  <p>SHA256: {detail.package_sha256 ?? "—"}</p>
                  <p>Byte size: {formatBytes(detail.byte_size)}</p>
                  <p>Artifacts: {detail.artifact_count}</p>
                  <p>Timeline events: {detail.timeline_event_count}</p>
                </section>

                <section className="rounded border p-3 dark:border-gray-700">
                  <h4 className="mb-2 font-medium">Duration</h4>
                  <p>{formatDuration(detail.generation_duration_seconds)}</p>
                </section>

                <section className="rounded border p-3 dark:border-gray-700">
                  <h4 className="mb-2 font-medium">Download audit history</h4>
                  {audit?.downloads.length ? (
                    <ul className="space-y-1 text-sm">
                      {audit.downloads.map((event, idx) => (
                        <li key={`${event.occurred_at_utc}-${idx}`} className="rounded border px-2 py-1 dark:border-gray-700">
                          <p>{formatDateTime(event.occurred_at_utc)}</p>
                          <p className="text-xs text-gray-500">{event.actor_type}</p>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-gray-500">No download events.</p>
                  )}
                </section>
              </div>
            )}
          </aside>
        </div>
      )}
    </MainLayout>
  );
}
