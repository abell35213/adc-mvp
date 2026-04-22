import Link from "next/link";
import type { CaseTaskWidgetItem } from "@/lib/api";

interface OverdueFollowUpListProps {
  items: CaseTaskWidgetItem[];
  loading: boolean;
  error: string;
}

export default function OverdueFollowUpList({
  items,
  loading,
  error,
}: OverdueFollowUpListProps) {
  return (
    <section className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Overdue follow-up list</h3>
      {loading && <p className="mt-2 text-sm text-gray-500">Loading overdue follow-ups…</p>}
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      {!loading && !error && items.length === 0 && <p className="mt-2 text-sm text-gray-500">No overdue follow-up tasks.</p>}
      {!loading && !error && items.length > 0 && (
        <ul className="mt-2 space-y-2 text-sm">
          {items.slice(0, 8).map((task) => (
            <li key={task.task_id}>
              <Link href={`/incidents/${task.incident_id}`} className="text-blue-600 hover:underline dark:text-blue-400">
                {task.title}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
