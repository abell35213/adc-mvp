"use client";

import { useEffect, useMemo, useState } from "react";
import MainLayout from "@/components/MainLayout";
import ExportListItem from "@/components/exports/ExportListItem";
import { downloadExport, listExports, retryExport, type ExportListItem as ExportItem, type ExportStatus, toUserErrorMessage } from "@/lib/api";
import { safeOpenDownloadUrl } from "@/lib/safeUrl";
import { designTokens } from "@/lib/design/tokens";

export default function ExportsPage() {
  const [exports, setExports] = useState<ExportItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"all" | ExportStatus>("all");

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
              <ExportListItem key={item.export_id} item={item} showIncident onDownload={handleDownload} onRetry={handleRetry} />
            ))}
          </div>
        )}
      </section>
    </MainLayout>
  );
}
