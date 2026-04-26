import type { IntegrationConnectionHealth } from "@/lib/api";

type Props = {
  connection: IntegrationConnectionHealth;
  onAction?: (action: "Validate" | "Reconnect" | "Details", connection: IntegrationConnectionHealth) => void;
};

const statusTone: Record<IntegrationConnectionHealth["status"], string> = {
  active: "bg-emerald-100 text-emerald-700",
  pending: "bg-amber-100 text-amber-700",
  inactive: "bg-gray-200 text-gray-700",
  error: "bg-red-100 text-red-700",
};

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : "—";
}

export default function IntegrationConnectionCard({ connection, onAction }: Props) {
  return (
    <article className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-50">{connection.provider}</h3>
          <p className="text-xs text-gray-500 dark:text-gray-300">{connection.domain ?? "unscoped domain"}</p>
        </div>
        <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase ${statusTone[connection.status]}`}>
          {connection.status}
        </span>
      </div>
      <dl className="mt-3 space-y-1 text-xs text-gray-600 dark:text-gray-300">
        <div className="flex justify-between gap-2">
          <dt>Connection state</dt>
          <dd className="font-medium">{connection.healthy ? "Connected" : "Action needed"}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Last check</dt>
          <dd className="font-medium">{formatDate(connection.updated_at_utc)}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Last sync</dt>
          <dd className="font-medium">{formatDate(connection.last_synced_at_utc)}</dd>
        </div>
      </dl>
      <div className="mt-3 flex flex-wrap gap-2">
        <button onClick={() => onAction?.("Validate", connection)} className="rounded border px-2 py-1 text-xs hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-700">Validate</button>
        <button onClick={() => onAction?.("Reconnect", connection)} className="rounded border px-2 py-1 text-xs hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-700">Reconnect</button>
        <button onClick={() => onAction?.("Details", connection)} className="rounded border px-2 py-1 text-xs hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-700">Details</button>
      </div>
    </article>
  );
}
