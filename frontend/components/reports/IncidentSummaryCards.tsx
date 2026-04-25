import type { CaseOpsSummaryMetrics } from "@/lib/api";

interface IncidentSummaryCardsProps {
  metrics: CaseOpsSummaryMetrics | null;
  loading: boolean;
}

const CARD_META: Array<{ key: keyof CaseOpsSummaryMetrics; label: string }> = [
  { key: "open_incidents", label: "Open incidents" },
  { key: "unassigned_incidents", label: "Unassigned" },
  { key: "blocked_incidents", label: "Blocked" },
  { key: "export_aging_incidents", label: "Export aging" },
  { key: "stalled_incidents", label: "Stalled" },
  { key: "overdue_tasks", label: "Overdue follow-ups" },
];

export default function IncidentSummaryCards({
  metrics,
  loading,
}: IncidentSummaryCardsProps) {
  return (
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {CARD_META.map((card) => (
        <article
          key={card.key}
          className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800"
        >
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
            {card.label}
          </p>
          <p className="mt-2 text-3xl font-semibold text-gray-900 dark:text-gray-100">
            {loading ? "…" : metrics?.[card.key] ?? 0}
          </p>
        </article>
      ))}
    </section>
  );
}
