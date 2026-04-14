import Link from "next/link";
import type { CaseOpsQueueItem } from "@/lib/api";

interface ExportReadyListProps {
  items: CaseOpsQueueItem[];
  loading: boolean;
}

export default function ExportReadyList({ items, loading }: ExportReadyListProps) {
  return (
    <section className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Export-ready list</h3>
      {loading && <p className="mt-2 text-sm text-gray-500">Loading export-ready incidents…</p>}
      {!loading && items.length === 0 && <p className="mt-2 text-sm text-gray-500">No incidents are ready for export.</p>}
      {!loading && items.length > 0 && (
        <ul className="mt-2 space-y-2 text-sm">
          {items.slice(0, 8).map((item) => (
            <li key={item.incident_id}>
              <Link href={`/incidents/${item.incident_id}`} className="text-blue-600 hover:underline dark:text-blue-400">
                {item.incident_id.slice(0, 8)}…
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
