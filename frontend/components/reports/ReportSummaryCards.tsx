interface ReportSummaryItem {
  id: string;
  label: string;
  value: string;
  detail: string;
  tone?: "neutral" | "success" | "warning" | "critical";
}

interface ReportSummaryCardsProps {
  items: ReportSummaryItem[];
}

const TONE_STYLES: Record<NonNullable<ReportSummaryItem["tone"]>, string> = {
  neutral: "border-border-subtle",
  success: "border-status-success/40",
  warning: "border-status-warning/40",
  critical: "border-status-critical/40",
};

export default function ReportSummaryCards({ items }: ReportSummaryCardsProps) {
  return (
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => {
        const tone = item.tone ?? "neutral";
        return (
          <article
            key={item.id}
            className={`rounded-lg border bg-surface p-4 shadow-card ${TONE_STYLES[tone]}`}
          >
            <p className="text-xs uppercase tracking-wide text-text-muted">{item.label}</p>
            <p className="mt-1 text-2xl font-semibold text-text-primary">{item.value}</p>
            <p className="mt-1 text-sm text-text-secondary">{item.detail}</p>
          </article>
        );
      })}
    </section>
  );
}
