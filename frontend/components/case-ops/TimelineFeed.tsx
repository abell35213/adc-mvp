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
    <section className="rounded-lg border bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-600">What happened timeline</h3>
      <ul className="mt-3 space-y-2 text-sm">
        {items.map((item, idx) => (
          <li key={`${item.source}-${item.type}-${idx}`} className="rounded-md border border-gray-200 p-2">
            <p className="font-medium text-gray-800">{item.source === "audit" ? "Ops" : "System"}: {item.type.replaceAll("_", " ")}</p>
            <p className="text-xs text-gray-500">{formatTime(item.occurred_at_utc)}</p>
          </li>
        ))}
        {items.length === 0 ? <li className="text-gray-500">No timeline activity yet.</li> : null}
      </ul>
    </section>
  );
}
