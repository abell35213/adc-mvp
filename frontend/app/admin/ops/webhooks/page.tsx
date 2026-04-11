"use client";

import { useEffect, useMemo, useState } from "react";
import AdminLayout from "@/components/AdminLayout";
import { getWebhookDiagnostics, type ProviderWebhookEvent } from "@/lib/api";

export default function WebhookDiagnosticsPage() {
  const [rows, setRows] = useState<ProviderWebhookEvent[]>([]);
  const [statusFilter, setStatusFilter] = useState("all");
  const [providerFilter, setProviderFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getWebhookDiagnostics({ limit: 200 })
      .then(setRows)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load webhook diagnostics"))
      .finally(() => setLoading(false));
  }, []);

  const providers = useMemo(() => Array.from(new Set(rows.map((row) => row.provider))).sort(), [rows]);

  const filtered = useMemo(
    () =>
      rows.filter((row) => {
        if (statusFilter !== "all" && row.status !== statusFilter) return false;
        if (providerFilter !== "all" && row.provider !== providerFilter) return false;
        return true;
      }),
    [rows, statusFilter, providerFilter]
  );

  return (
    <AdminLayout title="Webhook Diagnostics">
      <div className="space-y-4">
        <section className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-50">Internal operator diagnostics</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label className="text-xs">Status
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="mt-1 w-full rounded border px-2 py-1 dark:border-gray-600 dark:bg-gray-900">
                <option value="all">All statuses</option>
                <option value="accepted">Accepted</option>
                <option value="processed">Processed</option>
                <option value="failed">Failed</option>
                <option value="invalid_signature">Invalid signature</option>
              </select>
            </label>
            <label className="text-xs">Provider
              <select value={providerFilter} onChange={(e) => setProviderFilter(e.target.value)} className="mt-1 w-full rounded border px-2 py-1 dark:border-gray-600 dark:bg-gray-900">
                <option value="all">All providers</option>
                {providers.map((provider) => <option key={provider} value={provider}>{provider}</option>)}
              </select>
            </label>
          </div>
        </section>

        <section className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
          {loading && <p className="text-xs text-gray-500">Loading webhook events…</p>}
          {error && <p className="text-xs text-red-600">{error}</p>}
          <div className="overflow-x-auto">
            <table className="w-full min-w-[920px] text-left text-xs">
              <thead className="text-gray-500">
                <tr>
                  <th className="py-2">Received</th>
                  <th className="py-2">Provider</th>
                  <th className="py-2">Domain</th>
                  <th className="py-2">Status</th>
                  <th className="py-2">Latency (ms)</th>
                  <th className="py-2">Normalized code</th>
                  <th className="py-2">Retries</th>
                  <th className="py-2">Correlation</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-gray-700">
                {filtered.map((row) => (
                  <tr key={row.webhook_event_id}>
                    <td className="py-2">{new Date(row.received_at_utc).toLocaleString()}</td>
                    <td className="py-2">{row.provider}</td>
                    <td className="py-2">{row.domain ?? "—"}</td>
                    <td className="py-2">{row.status}</td>
                    <td className="py-2">{row.processing_latency_ms ?? "—"}</td>
                    <td className="py-2">{row.normalized_error_code ?? "NONE"}</td>
                    <td className="py-2">{row.retry_count ?? 0}</td>
                    <td className="py-2 font-mono">{row.correlation_id ?? "—"}</td>
                  </tr>
                ))}
                {!loading && filtered.length === 0 && (
                  <tr><td colSpan={8} className="py-4 text-gray-500">No webhook events found.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </AdminLayout>
  );
}
