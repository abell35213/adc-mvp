import type { CaseWorkspaceActivityItem } from "@/lib/api";

interface TimelineFeedProps {
  items: CaseWorkspaceActivityItem[];
}

function formatTime(iso?: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

export default function TimelineFeed({ items }: TimelineFeedProps) {
  return (
    <div className="rounded-lg border bg-white p-4 shadow dark:bg-gray-800">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">Timeline feed</h3>
      <ul className="mt-3 space-y-2 text-sm">
        {items.map((item, idx) => (
          <li key={`${item.source}-${item.type}-${idx}`} className="rounded border p-2 dark:border-gray-700">
            <p className="font-medium text-gray-800 dark:text-gray-200">
              {item.source === "audit" ? "Ops" : "System"}: {item.type}
            </p>
            <p className="text-xs text-gray-500">{formatTime(item.occurred_at_utc)}</p>
          </li>
        ))}
        {items.length === 0 && <li className="text-gray-500">No timeline activity.</li>}
      </ul>
    </div>
  );
}
