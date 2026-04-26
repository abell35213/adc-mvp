"use client";

import { useEffect, useMemo, useState } from "react";
import MainLayout from "@/components/MainLayout";
import ExportListItem from "@/components/exports/ExportListItem";
import { downloadExport, getExport, getExportContents, getExportDownloadHistory, listExports, retryExport, type ExportContentsItem, type ExportDownloadAuditResponse, type ExportListItem as ExportItem, type ExportStatus, type ExportSummary, toUserErrorMessage } from "@/lib/api";
import { safeOpenDownloadUrl } from "@/lib/safeUrl";
import { designTokens } from "@/lib/design/tokens";

export default function ExportsPage() {
  const [exports, setExports] = useState<ExportItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"all" | ExportStatus>("all");
  const [selectedExportId, setSelectedExportId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ExportSummary | null>(null);
  const [contents, setContents] = useState<ExportContentsItem[] | null>(null);
  const [audit, setAudit] = useState<ExportDownloadAuditResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    listExports()
      .then(setExports)
      .catch((err) => setError(toUserErrorMessage(err, "Failed to load exports")))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(
    () =>
      exports.filter((item) => {
        const matchesSearch =
          !query ||
          item.export_id.toLowerCase().includes(query.toLowerCase()) ||
          item.incident_id.toLowerCase().includes(query.toLowerCase()) ||
          (item.package_sha256 ?? "").toLowerCase().includes(query.toLowerCase());
        const matchesStatus = status === "all" || item.status === status;
        return matchesSearch && matchesStatus;
      }),
    [exports, query, status],
  );

  const counts = useMemo(() => ({
    queued: exports.filter((item) => item.status === "queued" || item.status === "requested").length,
    processing: exports.filter((item) => item.status === "processing").length,
    ready: exports.filter((item) => item.status === "ready").length,
    failed: exports.filter((item) => item.status === "failed" || item.status === "expired").length,
  }), [exports]);

  function getBlockedDownloadMessage(downloadUrl: string) {
    try {
      const { host } = new URL(downloadUrl);
      return `Download URL from unrecognized host "${host}" was blocked. Verify the export download configuration or contact support if this host should be allowed.`;
    } catch {
      return "Download URL from an unrecognized host was blocked. Verify the export download configuration or contact support if this URL should be allowed.";
    }
  }

  function formatBytes(size?: number | null) {
    if (size == null || size < 0) return "—";
    if (size < 1024) return `${size} B`;
    const units = ["KB", "MB", "GB", "TB"];
    let value = size / 1024;
    let unitIdx = 0;
    while (value >= 1024 && unitIdx < units.length - 1) { value /= 1024; unitIdx += 1; }
    return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[unitIdx]}`;
  }

  function formatDateTime(value?: string | null) {
    if (!value) return "—";
    return new Date(value).toLocaleString();
  }

  async function handleDetails(exportId: string) {
    setDetailLoading(true);
    setDetail(null);
    setContents(null);
    setAudit(null);
    setSelectedExportId(exportId);
    try {
      const [exportDetail, exportContents, exportAudit] = await Promise.all([
        getExport(exportId),
        getExportContents(exportId),
        getExportDownloadHistory(exportId),
      ]);
      setDetail(exportDetail);
      setContents(exportContents.file_manifest);
      setAudit(exportAudit);
    } catch (err: unknown) {
      setError(toUserErrorMessage(err, "Failed to load export detail"));
    } finally {
      setDetailLoading(false);
    }
  }

  async function handleRetry(exportId: string) {
    try {
      await retryExport(exportId);
      const updated = await listExports();
      setExports(updated);
    } catch (err: unknown) {
      setError(toUserErrorMessage(err, "Retry failed"));
    }
  }

  async function handleDownload(exportId: string) {
    try {
      const result = await downloadExport(exportId);
      const opened = safeOpenDownloadUrl(result.url);
      if (!opened) setError(getBlockedDownloadMessage(result.url));
    } catch (err: unknown) {
      setError(toUserErrorMessage(err, "Download failed"));
    }
  }

  return (
    <MainLayout title="Exports">
      <section className="space-y-4">
        <div>
          <h2 className="text-2xl font-semibold text-text-primary">Exports</h2>
          <p className="text-sm text-text-secondary">Track packet readiness, warnings, and package integrity.</p>
        </div>

        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {[
            ["Queued", counts.queued],
            ["Processing", counts.processing],
            ["Ready", counts.ready],
            ["Failed", counts.failed],
          ].map(([label, value]) => (
            <div key={label} className="rounded-lg border border-border-default bg-surface p-4 shadow-card">
              <p className="text-xs uppercase tracking-wide text-text-muted">{label}</p>
              <p className="mt-2 text-2xl font-semibold text-text-primary">{value}</p>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 gap-3 rounded-lg border border-border-default bg-surface p-3 shadow-card md:grid-cols-4">
          <input
            className={designTokens.control.input}
            placeholder="Filter by export, incident, or SHA"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <select className={designTokens.control.input} value={status} onChange={(e) => setStatus(e.target.value as typeof status)}>
            <option value="all">All statuses</option>
            <option value="requested">Requested</option>
            <option value="queued">Queued</option>
            <option value="processing">Processing</option>
            <option value="ready">Ready</option>
            <option value="failed">Failed</option>
            <option value="expired">Expired</option>
          </select>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}
        {loading ? (
          <p className="text-sm text-text-secondary">Loading exports…</p>
        ) : filtered.length === 0 ? (
          <p className="text-sm text-text-secondary">No exports match the selected filters.</p>
        ) : (
          <div className="space-y-3">
            {filtered.map((item) => (
              <ExportListItem key={item.export_id} item={item} showIncident onDownload={handleDownload} onRetry={handleRetry} onDetails={handleDetails} />
            ))}
          </div>
        )}
      </section>

      {selectedExportId && (
        <div className="fixed inset-0 z-40 flex justify-end bg-black/40">
          <aside className="h-full w-full max-w-2xl overflow-y-auto bg-surface p-4 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-text-primary">Export Detail</h3>
              <button
                onClick={() => setSelectedExportId(null)}
                className="rounded border border-border-default px-2 py-1 text-sm text-text-secondary hover:bg-surface-muted"
              >
                Close
              </button>
            </div>

            {detailLoading && <p className="text-sm text-text-secondary">Loading detail…</p>}
            {!detailLoading && detail && (
              <div className="space-y-4">
                <section className="rounded-lg border border-border-default p-3">
                  <h4 className="mb-2 font-medium text-text-primary">Metadata</h4>
                  <dl className="space-y-1 text-sm text-text-secondary">
                    <div><span className="font-medium text-text-primary">ID:</span> {detail.export_id}</div>
                    <div><span className="font-medium text-text-primary">Incident:</span> {detail.incident_id ?? "—"}</div>
                    <div><span className="font-medium text-text-primary">Type:</span> {detail.export_type}</div>
                    <div><span className="font-medium text-text-primary">Status:</span> {detail.status}</div>
                    <div><span className="font-medium text-text-primary">Created:</span> {formatDateTime(detail.created_at_utc)}</div>
                    <div><span className="font-medium text-text-primary">Completed:</span> {formatDateTime(detail.completed_at_utc)}</div>
                  </dl>
                </section>

                <section className="rounded-lg border border-border-default p-3">
                  <h4 className="mb-2 font-medium text-text-primary">Checksum &amp; counts</h4>
                  <dl className="space-y-1 text-sm text-text-secondary">
                    <div><span className="font-medium text-text-primary">SHA256:</span> {detail.package_sha256 ?? "—"}</div>
                    <div><span className="font-medium text-text-primary">Size:</span> {formatBytes(detail.byte_size)}</div>
                    <div><span className="font-medium text-text-primary">Artifacts:</span> {detail.artifact_count}</div>
                    <div><span className="font-medium text-text-primary">Timeline events:</span> {detail.timeline_event_count}</div>
                  </dl>
                </section>

                <section className="rounded-lg border border-border-default p-3">
                  <h4 className="mb-2 font-medium text-text-primary">Request options</h4>
                  <pre className="overflow-auto rounded-md bg-surface-muted p-2 text-xs text-text-secondary">
                    {JSON.stringify(detail.options_json ?? {}, null, 2)}
                  </pre>
                </section>

                {contents && (
                  <section className="grid gap-3 rounded-lg border border-border-default p-3 md:grid-cols-3">
                    {[
                      { label: "Included", items: contents.filter((f) => f.classification === "included") },
                      { label: "Excluded", items: contents.filter((f) => f.classification === "excluded_by_option") },
                      { label: "Unavailable", items: contents.filter((f) => f.classification === "unavailable" || f.classification === "failed_to_retrieve") },
                    ].map(({ label, items }) => (
                      <div key={label}>
                        <h4 className="mb-2 font-medium text-text-primary">{label} files</h4>
                        {items.length === 0 ? (
                          <p className="text-sm text-text-muted">None</p>
                        ) : (
                          <ul className="space-y-1">
                            {items.map((item) => (
                              <li key={`${item.kind}-${item.path ?? item.item ?? ""}`} className="rounded-md border border-border-default px-2 py-1 text-sm text-text-secondary">
                                <p className="font-medium">{item.item ?? item.kind}</p>
                                <p className="text-xs text-text-muted">{item.reason ?? "—"} · {formatBytes(item.byte_size)}</p>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    ))}
                  </section>
                )}

                <section className="rounded-lg border border-border-default p-3">
                  <h4 className="mb-2 font-medium text-text-primary">Download audit history</h4>
                  {audit?.downloads.length ? (
                    <ul className="space-y-1 text-sm text-text-secondary">
                      {audit.downloads.map((event, idx) => (
                        <li key={`${event.occurred_at_utc}-${idx}`} className="rounded-md border border-border-default px-2 py-1">
                          <p>{formatDateTime(event.occurred_at_utc)}</p>
                          <p className="text-xs text-text-muted">{event.actor_type}</p>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-text-muted">No download events.</p>
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
