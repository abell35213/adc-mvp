"use client";

import { useState } from "react";
import AdminLayout from "@/components/AdminLayout";
import { searchOpsAudit, type AuditSearchResponseItem } from "@/lib/api";

export default function AuditSearchPage() {
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<AuditSearchResponseItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const runSearch = async () => {
    setLoading(true);
    setError("");
    try {
      const results = await searchOpsAudit({ q, limit: 100, lookback_hours: 168 });
      setRows(results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to search audit events");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AdminLayout title="Audit Search">
      <div className="space-y-4">
        <div className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
          <label className="block text-xs font-medium uppercase text-gray-400">Search</label>
          <div className="mt-2 flex gap-2">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="actor_id, event_type, action"
              className="w-full rounded-md border px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-900"
            />
            <button
              onClick={runSearch}
              disabled={loading}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
            >
              {loading ? "Searching…" : "Search"}
            </button>
          </div>
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
        </div>

        <div className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
          <table className="w-full text-left text-xs">
            <thead className="text-gray-500">
              <tr>
                <th className="py-2">When</th>
                <th className="py-2">Actor</th>
                <th className="py-2">Event</th>
                <th className="py-2">Action</th>
                <th className="py-2">Outcome</th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-gray-700">
              {rows.map((row) => (
                <tr key={row.audit_event_id}>
                  <td className="py-2">{new Date(row.occurred_at_utc).toLocaleString()}</td>
                  <td className="py-2 font-mono">{row.actor_id}</td>
                  <td className="py-2">{row.event_type}</td>
                  <td className="py-2">{row.action}</td>
                  <td className="py-2">{row.outcome ?? "—"}</td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-4 text-gray-500">No results yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </AdminLayout>
  );
}
