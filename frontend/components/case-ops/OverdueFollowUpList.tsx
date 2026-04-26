import Link from "next/link";
import SectionCard from "@/components/layout/SectionCard";
import type { CaseTaskWidgetItem } from "@/lib/api";

interface OverdueFollowUpListProps {
  items: CaseTaskWidgetItem[];
  loading: boolean;
  error: string;
}

function formatDueDate(value?: string | null) {
  if (!value) return "No due date";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "No due date" : date.toLocaleString();
}

export default function OverdueFollowUpList({
  items,
  loading,
  error,
}: OverdueFollowUpListProps) {
  return (
    <SectionCard
      title="Overdue Follow-Ups"
      tone="warning"
      description="Tasks that are directly delaying case readiness."
    >
      {loading && <p className="text-sm text-text-secondary">Loading overdue follow-ups…</p>}
      {error && <p className="text-sm text-status-critical">{error}</p>}
      {!loading && !error && items.length === 0 && (
        <p className="text-sm text-text-secondary">No overdue follow-up tasks.</p>
      )}
      {!loading && !error && items.length > 0 && (
        <ul className="space-y-2 text-sm">
          {items.slice(0, 6).map((task) => (
            <li key={task.task_id} className="rounded-md border border-border-subtle bg-surface-raised px-3 py-2">
              <Link href={`/incidents/${task.incident_id}`} className="font-medium text-status-warning hover:underline">
                {task.title}
              </Link>
              <p className="text-xs text-text-secondary">
                {task.priority} priority · due {formatDueDate(task.due_at_utc)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}
