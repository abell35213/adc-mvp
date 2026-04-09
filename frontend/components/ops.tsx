"use client";

import Link from "next/link";
import type {
  IntegrationHealthItem,
  OpsAnomalyItem,
  OpsFailedNotificationItem,
} from "@/lib/api";

function formatDate(value?: string | null) {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString();
}

export function FailedJobsTable({
  rows,
}: {
  rows: OpsFailedNotificationItem[];
}) {
  return (
    <section className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-100">
        Failed Notifications
      </h2>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="text-gray-500">
            <tr>
              <th className="py-2">Task</th>
              <th className="py-2">Status</th>
              <th className="py-2">Retries</th>
              <th className="py-2">Updated</th>
              <th className="py-2">Error</th>
            </tr>
          </thead>
          <tbody className="divide-y dark:divide-gray-700">
            {rows.map((item) => (
              <tr key={item.celery_task_id}>
                <td className="py-2 font-mono text-[11px]">{item.celery_task_id}</td>
                <td className="py-2">{item.status}</td>
                <td className="py-2">
                  {item.retry_count}/{item.max_retries ?? "—"}
                </td>
                <td className="py-2">{formatDate(item.updated_at_utc)}</td>
                <td className="py-2 text-red-600">{item.last_error ?? "—"}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td className="py-4 text-gray-500" colSpan={5}>
                  No failed notifications.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function IntegrationHealthPanel({
  items,
}: {
  items: IntegrationHealthItem[];
}) {
  return (
    <section className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-100">
        Integration Health
      </h2>
      <ul className="mt-3 space-y-2 text-sm">
        {items.map((item) => (
          <li key={item.integration_key} className="rounded border p-3 dark:border-gray-700">
            <div className="flex items-center justify-between">
              <p className="font-medium text-gray-800 dark:text-gray-100">
                {item.integration_key}
              </p>
              <span
                className={`rounded-full px-2 py-0.5 text-xs ${
                  item.status === "healthy"
                    ? "bg-green-100 text-green-700"
                    : "bg-yellow-100 text-yellow-700"
                }`}
              >
                {item.status}
              </span>
            </div>
            <p className="text-xs text-gray-500">
              Failures: {item.failure_count} · Last failure: {formatDate(item.last_failure_at_utc)}
            </p>
            {item.details ? <p className="text-xs text-gray-500">{item.details}</p> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function SecurityAnomaliesPanel({
  items,
}: {
  items: OpsAnomalyItem[];
}) {
  return (
    <section className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-100">
          Recent Audit / Security Anomalies
        </h2>
        <Link href="/admin/ops/audit" className="text-xs text-blue-600 hover:underline">
          Open audit search
        </Link>
      </div>
      <ul className="mt-3 space-y-2 text-xs text-gray-600 dark:text-gray-300">
        {items.map((item) => (
          <li key={item.audit_event_id} className="rounded border p-3 dark:border-gray-700">
            <p>
              <span className="font-semibold">{item.event_type}</span> · {item.action}
            </p>
            <p>
              Actor {item.actor_id} · Outcome {item.outcome ?? "n/a"} · {formatDate(item.occurred_at_utc)}
            </p>
          </li>
        ))}
        {items.length === 0 && <li>No anomalies in lookback window.</li>}
      </ul>
    </section>
  );
}
